import os
import tempfile

import yaml
from jinja2 import Environment, FileSystemLoader
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    return LaunchDescription([
        DeclareLaunchArgument('robot_name', default_value='caddy_ai2',
                              description='Model name in Gazebo'),
        DeclareLaunchArgument('namespace',  default_value='',
                              description='ROS namespace for this robot'),
        DeclareLaunchArgument('prefix',     default_value='',
                              description='Link/joint name prefix in the SDF (e.g. robot1_)'),
        DeclareLaunchArgument('x',   default_value='0.0',
                              description='Spawn X position (m)'),
        DeclareLaunchArgument('y',   default_value='0.0',
                              description='Spawn Y position (m)'),
        DeclareLaunchArgument('z',   default_value='0.0',
                              description='Spawn Z above ground (m) — wheel_radius offset added automatically'),
        DeclareLaunchArgument('yaw', default_value='0.0',
                              description='Spawn yaw angle (rad)'),
        OpaqueFunction(function=_spawn_robot),
    ])


def _spawn_robot(context, *args, **kwargs):
    robot_name = context.launch_configurations['robot_name']
    namespace   = context.launch_configurations['namespace']
    prefix      = context.launch_configurations['prefix']
    x   = context.launch_configurations['x']
    y   = context.launch_configurations['y']
    z   = context.launch_configurations['z']
    yaw = context.launch_configurations['yaw']

    gz_share     = get_package_share_directory('caddy_ai2_ros2_gazebo_simulation')
    desc_share   = get_package_share_directory('caddy_ai2_ros2_description')
    sensor_share = get_package_share_directory('caddy_ai2_ros2_sensors_sick_lms_291')

    # --- Load robot physical parameters (single source of truth in description pkg) ---
    params_file = os.path.join(desc_share, 'config', 'robot_params.yaml')
    with open(params_file) as f:
        robot_params = yaml.safe_load(f)

    # --- Load SICK LMS 291 sensor parameters ---
    sensor_params_file = os.path.join(sensor_share, 'bringup', 'config', 'sensor_params.yaml')
    with open(sensor_params_file) as f:
        sensor_params = yaml.safe_load(f)

    spawn_z = str(float(z) + robot_params['wheel_radius'])

    # --- Render namespace-specific controllers yaml from Jinja2 template ---
    cfg_dir = os.path.join(gz_share, 'bringup', 'config')
    env = Environment(loader=FileSystemLoader(cfg_dir), keep_trailing_newline=True)

    rendered_ctrl = env.get_template('controllers_simulation.yaml.j2').render(
        namespace=namespace, prefix=prefix, **robot_params
    )
    tmp_ctrl = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', prefix='ctrl_ns_', delete=False
    )
    tmp_ctrl.write(rendered_ctrl)
    tmp_ctrl.close()
    ns_controllers_yaml = tmp_ctrl.name

    # --- Render namespace-specific gz bridge yaml from Jinja2 template ---
    rendered_bridge = env.get_template('gz_msg_bridge.yaml.j2').render(namespace=namespace)
    tmp_bridge = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', prefix='gz_bridge_ns_', delete=False
    )
    tmp_bridge.write(rendered_bridge)
    tmp_bridge.close()
    ns_bridge_yaml = tmp_bridge.name

    # --- Render SICK LMS 291 SDF fragment ---
    hw = sensor_params['hardware']
    op = sensor_params['operation']
    si = sensor_params['simulation']
    no = si['noise']

    sensor_env = Environment(
        loader=FileSystemLoader(os.path.join(sensor_share, 'description')),
        keep_trailing_newline=True,
    )
    sick_lidar_fragment = sensor_env.get_template('sensor.sdf.j2').render(
        prefix=prefix,
        namespace=namespace,
        parent_link=f'{prefix}base_link',
        x=robot_params['lidar_sick_x'],
        y=robot_params['lidar_sick_y'],
        z=robot_params['lidar_sick_z'],
        roll=robot_params['lidar_sick_roll'],
        pitch=robot_params['lidar_sick_pitch'],
        yaw=robot_params['lidar_sick_yaw'],
        frame_id=hw['frame_id'],
        weight=hw['weight'],
        angle_min=si['angle_min'],
        angle_max=si['angle_max'],
        range_min=si['range_min'],
        range_max=si['range_max'],
        frequency=op['frequency'],
        resolution=op['resolution'],
        use_gpu=True,
        mesh_uri=f'package://caddy_ai2_ros2_sensors_sick_lms_291/meshes/SICK_LMS291-S05.dae',
        noise_enabled=no['enabled'],
        noise_type=no['type'],
        noise_mean=no['mean'],
        noise_stddev=no['stddev'],
        noise_bias_mean=no['bias_mean'],
        noise_bias_stddev=no['bias_stddev'],
    )

    # --- Render SDF model from Jinja2 template ---
    sdf_dir = os.path.join(gz_share, 'description', 'sdf')
    env_sdf = Environment(loader=FileSystemLoader(sdf_dir), keep_trailing_newline=True)
    robot_description_str = env_sdf.get_template('caddy_ai2_model.sdf.j2').render(
        namespace=namespace,
        prefix=prefix,
        controllers_yaml_path=ns_controllers_yaml,
        sick_lidar_fragment=sick_lidar_fragment,
        **robot_params,
    )

    rd_topic = f'/{namespace}/robot_description' if namespace else '/robot_description'

    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        namespace=namespace,
        output='screen',
        parameters=[{
            'robot_description': robot_description_str,
            'use_sim_time': True,
        }]
    )

    gz_spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=[
            '-topic', rd_topic,
            '-name',  robot_name,
            '-x', x,
            '-y', y,
            '-z', spawn_z,
            '-Y', yaw,
        ]
    )

    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        namespace=namespace,
        arguments=['joint_state_broadcaster'],
    )

    ackermann_steering_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        namespace=namespace,
        arguments=['bicycle_to_ackermann_steering_adapter',
                   '--param-file', ns_controllers_yaml],
    )

    ackermann_traction_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        namespace=namespace,
        arguments=['bicycle_to_ackermann_traction_adapter',
                   '--param-file', ns_controllers_yaml],
    )

    bicycle_steering_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        namespace=namespace,
        arguments=['bicycle_steering_controller',
                   '--param-file', ns_controllers_yaml],
    )

    forward_position_command_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        namespace=namespace,
        arguments=['forward_position_command_controller',
                   '--param-file', ns_controllers_yaml,
                   '--inactive'],
    )

    forward_velocity_command_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        namespace=namespace,
        arguments=['forward_velocity_command_controller',
                   '--param-file', ns_controllers_yaml,
                   '--inactive'],
    )

    sensor_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='sensor_bridge',
        namespace=namespace,
        parameters=[{'config_file': ns_bridge_yaml}],
        output='screen'
    )

    return [
        node_robot_state_publisher,
        gz_spawn_entity,
        sensor_bridge,
        RegisterEventHandler(
            OnProcessExit(
                target_action=gz_spawn_entity,
                on_exit=[joint_state_broadcaster_spawner],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=joint_state_broadcaster_spawner,
                on_exit=[ackermann_steering_controller_spawner],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=ackermann_steering_controller_spawner,
                on_exit=[ackermann_traction_controller_spawner],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=ackermann_traction_controller_spawner,
                on_exit=[bicycle_steering_controller_spawner],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=bicycle_steering_controller_spawner,
                on_exit=[
                    forward_position_command_controller_spawner,
                    forward_velocity_command_controller_spawner,
                ],
            )
        ),
    ]
