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
        description='World SDF filename (relative to description/world/) or absolute path'
    )

    gz_resource_path_arg = DeclareLaunchArgument(
        'gz_resource_path',
        default_value='',
        description='Extra directory prepended to GZ_SIM_RESOURCE_PATH (e.g. ~/PX4-gazebo-models)'
    )

    def launch_gz_sim(context, *args, **kwargs):
        pkg_share = get_package_share_directory('caddy_ai2_ros2_gazebo_simulation')
        world_value = context.launch_configurations['world']
        extra_resource_path = context.launch_configurations.get('gz_resource_path', '')

        # Accept both absolute paths and filenames relative to description/world/
        if os.path.isabs(world_value):
            world_sdf = world_value
        else:
            world_sdf = os.path.join(pkg_share, 'description', 'world', world_value)

        # Build GZ_SIM_RESOURCE_PATH: extra path + package share + existing env
        pkg_prefix_share = os.path.join(
            os.path.dirname(os.path.dirname(pkg_share)), 'share'
        )
        existing = os.environ.get('GZ_SIM_RESOURCE_PATH', '')
        parts = [p for p in [extra_resource_path, pkg_prefix_share, existing] if p]
        resource_path = os.pathsep.join(parts)

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

        set_resource_path = SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', resource_path)

        return [set_resource_path, gz_sim, clock_bridge]

    return LaunchDescription([
        world_arg,
        gz_resource_path_arg,
        OpaqueFunction(function=launch_gz_sim),
    ])
