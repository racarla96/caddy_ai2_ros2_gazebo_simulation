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
                              description='Spawn Z above ground (m)'),
        DeclareLaunchArgument('yaw', default_value='0.0',
                              description='Spawn yaw angle (rad)'),
        OpaqueFunction(function=_spawn_robot),
    ])


def _render_sensor_fragments(robot_params, prefix, gazebo=False, namespace=''):
    """Render per-sensor URDF fragments. gazebo=True adds Gazebo sensor plugins."""
    fragments = []
    for sensor_name, sensor_cfg in robot_params.get('sensors', {}).items():
        if not sensor_cfg.get('enabled', True):
            continue
        sensor_type = sensor_cfg['type']
        s_share = get_package_share_directory(sensor_cfg['package'])
        urdf_tpl = os.path.join(s_share, 'description', 'sensor.urdf.j2')
        if not os.path.isfile(urdf_tpl):
            continue
        pose = sensor_cfg['pose']
        s_env = Environment(
            loader=FileSystemLoader(os.path.join(s_share, 'description')),
            keep_trailing_newline=True,
        )
        render_kwargs = dict(
            prefix=prefix,
            sensor_name=sensor_name,
            sensor_type=sensor_type,
            frame_id=sensor_cfg['frame_id'],
            x=pose['x'], y=pose['y'], z=pose['z'],
            roll=pose['roll'], pitch=pose['pitch'], yaw=pose['yaw'],
            sensor_share=s_share,
            gazebo=gazebo,
        )
        if gazebo:
            sensor_params_file = os.path.join(s_share, 'bringup', 'config', 'sensor_params.yaml')
            with open(sensor_params_file) as f:
                sp = yaml.safe_load(f)
            if sensor_type in ('range_lidar', 'lidar_2d'):
                si, op, no = sp['simulation'], sp['operation'], sp['simulation']['noise']
                render_kwargs.update(
                    namespace=namespace,
                    angle_min=si['angle_min'], angle_max=si['angle_max'],
                    range_min=si['range_min'], range_max=si['range_max'],
                    frequency=op['frequency'], resolution=op['resolution'],
                    use_gpu=True,
                    noise_enabled=no['enabled'], noise_mean=no['mean'], noise_stddev=no['stddev'],
                )
            elif sensor_type == 'imu':
                si, no = sp['simulation'], sp['simulation']['noise']
                render_kwargs.update(
                    namespace=namespace,
                    update_rate=si['update_rate'],
                    noise_enabled=True,
                    gyro_mean=no['gyro']['mean'], gyro_stddev=no['gyro']['stddev'],
                    accel_mean=no['accel']['mean'], accel_stddev=no['accel']['stddev'],
                )
            elif sensor_type == 'gps':
                si = sp['simulation']
                render_kwargs.update(
                    namespace=namespace,
                    update_rate=si.get('gps_update_rate', 5),
                )
        fragments.append(s_env.get_template('sensor.urdf.j2').render(**render_kwargs))
    return '\n'.join(fragments)


def _spawn_robot(context):
    robot_name = context.launch_configurations['robot_name']
    namespace   = context.launch_configurations['namespace']
    prefix      = context.launch_configurations['prefix']
    x   = context.launch_configurations['x']
    y   = context.launch_configurations['y']
    z   = context.launch_configurations['z']
    yaw = context.launch_configurations['yaw']

    gz_share   = get_package_share_directory('caddy_ai2_ros2_gazebo_simulation')
    desc_share = get_package_share_directory('caddy_ai2_ros2_description')

    # --- Load robot physical parameters ---
    params_file = os.path.join(desc_share, 'bringup', 'config', 'robot_params.yaml')
    with open(params_file) as f:
        robot_params = yaml.safe_load(f)

    # --- Render controllers yaml ---
    cfg_dir = os.path.join(gz_share, 'bringup', 'config')
    env = Environment(loader=FileSystemLoader(cfg_dir), keep_trailing_newline=True)
    rendered_ctrl = env.get_template('controllers_simulation.yaml.j2').render(
        namespace=namespace, prefix=prefix, **robot_params
    )
    tmp_ctrl = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', prefix='ctrl_ns_', delete=False)
    tmp_ctrl.write(rendered_ctrl)
    tmp_ctrl.close()
    ns_controllers_yaml = tmp_ctrl.name

    # --- Render gz bridge yaml ---
    rendered_bridge = env.get_template('gz_msg_bridge.yaml.j2').render(
        namespace=namespace,
        prefix=prefix,
        sensors=robot_params.get('sensors', {}),
    )
    tmp_bridge = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', prefix='gz_bridge_ns_', delete=False)
    tmp_bridge.write(rendered_bridge)
    tmp_bridge.close()
    ns_bridge_yaml = tmp_bridge.name

    gz_urdf_dir   = os.path.join(gz_share,   'description', 'model', 'urdf')
    desc_urdf_dir = os.path.join(desc_share, 'description', 'model', 'urdf')

    # --- Render Gazebo URDF (sim template + sensor plugins) ---
    env_gz_urdf = Environment(
        loader=FileSystemLoader([gz_urdf_dir, desc_urdf_dir]),
        keep_trailing_newline=True,
    )
    robot_description_gz_str = env_gz_urdf.get_template('caddy_ai2_model_sim.urdf.j2').render(
        simulation=True,
        namespace=namespace,
        prefix=prefix,
        controllers_yaml_path=ns_controllers_yaml,
        sensors_urdf_fragment=_render_sensor_fragments(robot_params, prefix, gazebo=True, namespace=namespace),
        desc_share=desc_share,
        **robot_params,
    )

    # --- Render display URDF (base template, no Gazebo/ros2_control plugins) ---
    env_desc_urdf = Environment(
        loader=FileSystemLoader(desc_urdf_dir),
        keep_trailing_newline=True,
    )
    robot_description_display_str = env_desc_urdf.get_template('caddy_ai2_model.urdf.j2').render(
        namespace=namespace,
        prefix=prefix,
        sensors_urdf_fragment=_render_sensor_fragments(robot_params, prefix, gazebo=False),
        desc_share=desc_share,
        **robot_params,
    )

    rd_topic = f'/{namespace}/robot_description' if namespace else '/robot_description'

    # RSP for Gazebo + TF broadcasting
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        namespace=namespace,
        output='screen',
        parameters=[{
            'robot_description': robot_description_gz_str,
            'use_sim_time': True,
        }],
    )

    # Publishes clean URDF (no Gazebo plugins) for RViz — no TF, no joint states
    node_robot_description_publisher_rviz = Node(
        package='caddy_ai2_ros2_robot_description_publisher',
        executable='caddy_ai2_ros2_robot_description_publisher',
        name='robot_description_publisher_rviz',
        namespace=namespace,
        output='screen',
        parameters=[{
            'robot_description': robot_description_display_str,
            'robot_description_topic': 'robot_description_rviz',
        }],
    )

    node_rviz2 = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        namespace=namespace,
        output='screen',
        arguments=['-d', os.path.join(gz_share, 'bringup', 'rviz', 'caddy.rviz')],
        parameters=[{'use_sim_time': True}],
    )

    gz_spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=[
            '-topic', rd_topic,
            '-name',  robot_name,
            '-x', x, '-y', y, '-z', z, '-Y', yaw,
        ]
    )

    sensor_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='sensor_bridge',
        namespace=namespace,
        parameters=[{'config_file': ns_bridge_yaml}],
        output='screen',
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
        arguments=['bicycle_to_ackermann_steering_adapter', '--param-file', ns_controllers_yaml],
    )

    ackermann_traction_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        namespace=namespace,
        arguments=['bicycle_to_ackermann_traction_adapter', '--param-file', ns_controllers_yaml],
    )

    bicycle_steering_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        namespace=namespace,
        arguments=['bicycle_steering_controller', '--param-file', ns_controllers_yaml],
    )

    return [
        node_robot_state_publisher,
        node_robot_description_publisher_rviz,
        node_rviz2,
        gz_spawn_entity,
        RegisterEventHandler(OnProcessExit(
            target_action=gz_spawn_entity,
            on_exit=[sensor_bridge, joint_state_broadcaster_spawner],
        )),
        RegisterEventHandler(OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[ackermann_steering_controller_spawner],
        )),
        RegisterEventHandler(OnProcessExit(
            target_action=ackermann_steering_controller_spawner,
            on_exit=[ackermann_traction_controller_spawner],
        )),
        RegisterEventHandler(OnProcessExit(
            target_action=ackermann_traction_controller_spawner,
            on_exit=[bicycle_steering_controller_spawner],
        )),
    ]
