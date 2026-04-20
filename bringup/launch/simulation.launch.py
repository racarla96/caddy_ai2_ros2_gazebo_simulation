from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    return LaunchDescription([
        # World arguments
        DeclareLaunchArgument('world', default_value='caddy_ai2_world.sdf.xacro',
                              description='World xacro file name inside description/sdf/'),

        # Robot spawn arguments
        DeclareLaunchArgument('robot_name', default_value='caddy_ai2'),
        DeclareLaunchArgument('namespace',  default_value=''),
        DeclareLaunchArgument('prefix',     default_value=''),
        DeclareLaunchArgument('x',   default_value='0.0'),
        DeclareLaunchArgument('y',   default_value='0.0'),
        DeclareLaunchArgument('z',   default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),

        # Launch Gazebo with the world
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('caddy_ai2_ros2_gazebo_simulation'),
                    'bringup', 'launch', 'world.launch.py'
                ])
            ]),
            launch_arguments={
                'world': LaunchConfiguration('world'),
            }.items()
        ),

        # Spawn one robot
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('caddy_ai2_ros2_gazebo_simulation'),
                    'bringup', 'launch', 'spawn_robot.launch.py'
                ])
            ]),
            launch_arguments={
                'robot_name': LaunchConfiguration('robot_name'),
                'namespace':  LaunchConfiguration('namespace'),
                'prefix':     LaunchConfiguration('prefix'),
                'x':   LaunchConfiguration('x'),
                'y':   LaunchConfiguration('y'),
                'z':   LaunchConfiguration('z'),
                'yaw': LaunchConfiguration('yaw'),
            }.items()
        ),
    ])
