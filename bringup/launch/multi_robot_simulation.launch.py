"""
multi_robot_simulation.launch.py
─────────────────────────────────────────────────────────────────────────────
Launches Gazebo with the configured world and spawns every robot defined in
multi_robot_config.yaml.

Usage
-----
  ros2 launch caddy_ai2_ros2_gazebo_simulation multi_robot_simulation.launch.py

Optional overrides
------------------
  world:=<xacro_filename>          (default: caddy_ai2_world.sdf.xacro)
  robots_config:=<absolute_path>   (default: <pkg>/bringup/config/multi_robot_config.yaml)
"""

import os

import yaml
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare



def _spawn_all_robots(context, *args, **kwargs):
    """
    OpaqueFunction that reads the robots YAML at launch time and returns one
    spawn_robot.launch.py IncludeLaunchDescription per robot entry.
    """
    pkg_share = get_package_share_directory('caddy_ai2_ros2_gazebo_simulation')

    # Resolve the config file path (may be overridden via launch argument)
    robots_config_path = context.launch_configurations.get(
        'robots_config',
        os.path.join(pkg_share, 'bringup', 'config', 'multi_robot_config.yaml'),
    )

    with open(robots_config_path, 'r') as f:
        config = yaml.safe_load(f)

    robots = config.get('robots', [])
    if not robots:
        raise RuntimeError(
            f"No robots found in config file: {robots_config_path}\n"
            "Make sure the file has a top-level 'robots:' list."
        )

    spawn_robot_launch = PathJoinSubstitution([
        FindPackageShare('caddy_ai2_ros2_gazebo_simulation'),
        'bringup', 'launch', 'spawn_robot.launch.py',
    ])

    actions = []
    for robot in robots:
        # Validate required keys
        required_keys = ('robot_name', 'namespace', 'prefix', 'x', 'y', 'z', 'yaw')
        missing = [k for k in required_keys if k not in robot]
        if missing:
            raise RuntimeError(
                f"Robot entry is missing required keys {missing}: {robot}"
            )

        actions.append(
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(spawn_robot_launch),
                launch_arguments={
                    'robot_name': str(robot['robot_name']),
                    'namespace':  str(robot['namespace']),
                    'prefix':     str(robot['prefix']),
                    'x':   str(robot['x']),
                    'y':   str(robot['y']),
                    'z':   str(robot['z']),
                    'yaw': str(robot['yaw']),
                }.items(),
            )
        )

    return actions



def generate_launch_description():

    pkg_share = get_package_share_directory('caddy_ai2_ros2_gazebo_simulation')
    default_config = os.path.join(
        pkg_share, 'bringup', 'config', 'multi_robot_config.yaml'
    )

    return LaunchDescription([

        # World argument
        DeclareLaunchArgument(
            'world',
            default_value='caddy_ai2_world.sdf.xacro',
            description='World xacro file name inside description/sdf/',
        ),

        # Robots config argument
        DeclareLaunchArgument(
            'robots_config',
            default_value=default_config,
            description='Absolute path to the multi_robot_config.yaml file',
        ),

        # Launch Gazebo with the world
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('caddy_ai2_ros2_gazebo_simulation'),
                    'bringup', 'launch', 'world.launch.py',
                ])
            ]),
            launch_arguments={
                'world': LaunchConfiguration('world'),
            }.items(),
        ),

        # Spawn all robots defined in the YAML
        OpaqueFunction(function=_spawn_all_robots),
    ])