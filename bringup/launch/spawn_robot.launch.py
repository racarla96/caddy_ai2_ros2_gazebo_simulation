import os
import subprocess
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

    pkg_share = get_package_share_directory('caddy_ai2_ros2_gazebo_simulation')

    # --- Load robot physical parameters ---
    params_file = os.path.join(pkg_share, 'bringup', 'config', 'robot_params.yaml')
    with open(params_file) as f:
        robot_params = yaml.safe_load(f)

    spawn_z = str(float(z) + robot_params['wheel_radius'])

    model_xacro = os.path.join(pkg_share, 'description', 'sdf', 'caddy_ai2_model.sdf.xacro')
    config_dir  = os.path.join(pkg_share, 'bringup', 'config')

    # --- Process model xacro, passing physical params as arguments ---
    result = subprocess.run(
        [
            'xacro', model_xacro,
            f'prefix:={prefix}',
            f'namespace:={namespace}',
            f'wheelbase:={robot_params["wheelbase"]}',
            f'track_width:={robot_params["track_width"]}',
            f'wheel_radius:={robot_params["wheel_radius"]}',
            f'max_steer_angle:={robot_params["max_steer_angle"]}',
            f'wheel_width:={robot_params["wheel_width"]}',
            f'wheel_mass:={robot_params["wheel_mass"]}',
            f'height:={robot_params["height"]}',
            f'mass:={robot_params["mass"]}',
            f'vehicle_collision_width:={robot_params["vehicle_collision_width"]}',
            f'vehicle_collision_length:={robot_params["vehicle_collision_length"]}',
            f'vehicle_collision_height:={robot_params["vehicle_collision_height"]}',
            f'vehicle_collision_offset_x:={robot_params["vehicle_collision_offset_x"]}',
            f'inertial_origin_offset_x:={robot_params["inertial_origin_offset_x"]}',
        ],
        capture_output=True, text=True, check=True
    )
    robot_description_str = result.stdout

    # --- Render namespace-specific controllers yaml from Jinja2 template ---
    env = Environment(loader=FileSystemLoader(config_dir), keep_trailing_newline=True)
    template = env.get_template('controllers_simulation.yaml.j2')
    rendered_yaml = template.render(namespace=namespace, prefix=prefix, **robot_params)

    tmp_yaml = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', prefix='ctrl_ns_', delete=False
    )
    tmp_yaml.write(rendered_yaml)
    tmp_yaml.close()
    ns_controllers_yaml = tmp_yaml.name

    # --- Render namespace-specific gz bridge yaml from Jinja2 template ---
    bridge_template = env.get_template('gz_msg_bridge.yaml.j2')
    rendered_bridge_yaml = bridge_template.render(namespace=namespace)

    tmp_bridge_yaml = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', prefix='gz_bridge_ns_', delete=False
    )
    tmp_bridge_yaml.write(rendered_bridge_yaml)
    tmp_bridge_yaml.close()
    ns_bridge_yaml = tmp_bridge_yaml.name

    # Replace the original <parameters> path in the SDF with the rendered yaml
    original_params_tag = (
        f'<parameters>'
        f'{os.path.join(pkg_share, "bringup", "config", "controllers_simulation.yaml")}'
        f'</parameters>'
    )
    robot_description_str = robot_description_str.replace(
        original_params_tag,
        f'<parameters>{ns_controllers_yaml}</parameters>',
        1,
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
