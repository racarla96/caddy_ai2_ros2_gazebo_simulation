import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.actions import SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare, FindPackagePrefix


def generate_launch_description():

    world_arg = DeclareLaunchArgument(
        'world',
        default_value='caddy_ai2_world.sdf',
        description='World SDF file name inside description/world/'
    )

    def launch_gz_sim(context, *args, **kwargs):
        pkg_share = get_package_share_directory('caddy_ai2_ros2_gazebo_simulation')
        world_filename = context.launch_configurations['world']
        world_sdf = os.path.join(pkg_share, 'description', 'world', world_filename)

        gz_sim = IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py'
                ])
            ]),
            launch_arguments={'gz_args': f'-r {world_sdf}'}.items()
        )

        clock_bridge = Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='clock_bridge',
            arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
            output='screen'
        )

        return [gz_sim, clock_bridge]

    return LaunchDescription([
        SetEnvironmentVariable(
            'GZ_SIM_RESOURCE_PATH',
            PathJoinSubstitution([
                FindPackagePrefix('caddy_ai2_ros2_gazebo_simulation'),
                'share'
            ])
        ),
        world_arg,
        OpaqueFunction(function=launch_gz_sim),
    ])
