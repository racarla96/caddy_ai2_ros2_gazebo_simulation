from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.parameter_descriptions import ParameterValue
from launch.actions import SetEnvironmentVariable
from launch_ros.substitutions import FindPackagePrefix

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # Launch Arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default=True)

    def robot_state_publisher(context):
        # Get URDF via xacro
        robot_description_content = ParameterValue(
            Command(
                [
                    PathJoinSubstitution([FindExecutable(name='xacro')]),
                    ' ',
                    PathJoinSubstitution([
                        FindPackageShare('caddy_ai2_ros2_gazebo_simulation'),
                        'description',
                        'sdf',
                        'caddy_ai2_model.sdf.xacro'
                    ]),
                ]
            ),
            value_type=str
        )
        robot_description = {'robot_description': robot_description_content}
        node_robot_state_publisher = Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[robot_description]
        )
        return [node_robot_state_publisher]

    robot_controllers = PathJoinSubstitution(
        [
            FindPackageShare('caddy_ai2_ros2_gazebo_simulation'),
            'bringup',
            'config',
            'controllers_simulation.yaml',
        ]
    )

    gz_spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=['-topic', 'robot_description'],
    )

    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster'],
    )

    ackermann_steering_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['bicycle_to_ackermann_steering_adapter',
                   '--param-file',
                   robot_controllers,
                   ],
    )

    ackermann_traction_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['bicycle_to_ackermann_traction_adapter',
                   '--param-file',
                   robot_controllers,
                   ],
    )

    forward_position_command_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['forward_position_command_controller',
                   '--param-file',
                   robot_controllers,
                   ],
    )

    forward_velocity_command_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['forward_velocity_command_controller',
                   '--param-file',
                   robot_controllers,
                   ],
    )

    bicycle_steering_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['bicycle_steering_controller',
                   '--param-file',
                   robot_controllers,
                   ],
    )

    # Bridge
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen'
    )

    ld = LaunchDescription([
        SetEnvironmentVariable(
            'GZ_SIM_RESOURCE_PATH',
            PathJoinSubstitution([
                FindPackagePrefix('caddy_ai2_ros2_gazebo_simulation'),
                'share'
            ])
        ),
        bridge,
        # Launch gazebo environment
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=gz_spawn_entity,
                on_exit=[joint_state_broadcaster_spawner],
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=joint_state_broadcaster_spawner,
                on_exit=[ackermann_steering_controller_spawner],
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=ackermann_steering_controller_spawner,
                on_exit=[ackermann_traction_controller_spawner],
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=ackermann_traction_controller_spawner,
                on_exit=[bicycle_steering_controller_spawner],
            )
        ),
        gz_spawn_entity,
        # Launch Arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value=use_sim_time,
            description='If true, use simulated clock'),
    ])
    ld.add_action(OpaqueFunction(function=robot_state_publisher))
    return ld