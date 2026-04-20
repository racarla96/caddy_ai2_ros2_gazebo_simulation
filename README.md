# Caddy AI2 ROS2 Gazebo Simulation

## Estructura del paquete

```
caddy_ai2_ros2_gazebo_simulation/
├── bringup/
│   ├── config/
│   │   ├── controllers_simulation.yaml   # Configuración de ros2_control
│   │   └── gz_msg_bridge.yaml            # Bridges de mensajes Gazebo ↔ ROS2
│   └── launch/
│       ├── world.launch.py               # Lanza Gazebo con el world (sin robots)
│       ├── spawn_robot.launch.py         # Spawna una instancia de robot
│       └── simulation.launch.py          # World + un robot (caso por defecto)
└── description/
    └── sdf/
        ├── caddy_ai2_model.sdf.xacro     # Macro del modelo del robot
        ├── caddy_ai2_model_spawn.sdf.xacro  # Wrapper para spawn individual
        ├── caddy_ai2_world.sdf.xacro     # World (sin robots embebidos)
        └── materials.sdf.xacro           # Colores / materiales
```

## Build

```bash
colcon build --packages-select \
  bicycle_to_ackermann_steering_adapter \
  bicycle_to_ackermann_traction_adapter \
  caddy_ai2_ros2_gazebo_simulation
source install/setup.bash
```

## Simulación — robot único

```bash
ros2 launch caddy_ai2_ros2_gazebo_simulation simulation.launch.py
```

Argumentos disponibles:

| Argumento     | Descripción                              | Por defecto               |
|---------------|------------------------------------------|---------------------------|
| `world`       | Fichero xacro del world (en `description/sdf/`) | `caddy_ai2_world.sdf.xacro` |
| `robot_name`  | Nombre del modelo en Gazebo              | `caddy_ai2`               |
| `namespace`   | Namespace ROS2 del robot                 | `` (vacío)                |
| `prefix`      | Prefijo para nombres de links y joints   | `` (vacío)                |
| `x`, `y`, `z` | Posición de spawn (m)                    | `0.0`                     |
| `yaw`         | Orientación de spawn (rad)               | `0.0`                     |

## Simulación — multi-robot

El world y el spawn de robots están separados para poder lanzar N robots de forma independiente.

**Paso 1 — lanzar el world (una sola vez):**

```bash
ros2 launch caddy_ai2_ros2_gazebo_simulation world.launch.py
```

**Paso 2 — spawnar cada robot en un terminal distinto:**

```bash
# Robot 1
ros2 launch caddy_ai2_ros2_gazebo_simulation spawn_robot.launch.py \
  robot_name:=robot1 namespace:=robot1 prefix:=robot1_ x:=0.0 y:=0.0

# Robot 2
ros2 launch caddy_ai2_ros2_gazebo_simulation spawn_robot.launch.py \
  robot_name:=robot2 namespace:=robot2 prefix:=robot2_ x:=3.0 y:=0.0
```

Cada instancia crea su propio `controller_manager` bajo `/<namespace>/controller_manager` gracias al plugin `gz_ros2_control` configurado con el namespace en el SDF.

## Control manual

Publicar referencia de velocidad y dirección (con namespace `robot1`):

```bash
# Bicycle steering controller
ros2 topic pub /robot1/bicycle_steering_controller/reference geometry_msgs/msg/TwistStamped "
header:
  frame_id: 'robot1_base_link'
twist:
  linear:
    x: 1.0
  angular:
    z: 0.5
"

# Controladores directos (forward command) — alternativos al bicycle_steering_controller.
# Se cargan inactivos para evitar conflicto de interfaces. Activar tras desactivar bicycle_steering_controller:
ros2 control switch_controllers --deactivate bicycle_steering_controller --activate forward_position_command_controller forward_velocity_command_controller --controller-manager /robot1/controller_manager

ros2 topic pub /robot1/forward_position_command_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.3]}" -r 100
ros2 topic pub /robot1/forward_velocity_command_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.3]}" -r 100
```

Sin namespace (robot único con `simulation.launch.py` por defecto):

```bash
ros2 topic pub /bicycle_steering_controller/reference geometry_msgs/msg/TwistStamped "
header:
  frame_id: 'base_link'
twist:
  linear:
    x: 1.0
  angular:
    z: 0.5
"
```

## Medidas del vehículo

![Plano del vehículo](doc/img/caddy_plane.png)

![Concepto del vehículo](doc/img/car_concept.jpeg)

## Modelo visual (chassis STL)

El archivo STL del chassis tiene un alineamiento definido respecto a los ejes del vehículo, pero no tiene en cuenta el centro de masas. Para el aspecto visual se aplica un alineamiento considerando las medidas aproximadas y la escala del modelo.

El wheelbase en el modelo visual es 16.50 mm (escala 1:100), equivalente a 1650 mm = 1.65 m en el real.

![Alineamiento 1](doc/img/chassis_stl_align_1.png)
![Alineamiento 2](doc/img/chassis_stl_align_2.png)
![Alineamiento 3](doc/img/chassis_stl_align_3.png)
![Alineamiento 4](doc/img/chassis_stl_align_4.png)

## TODOs

- [ ] Medir aspectos reales del vehículo (centro de gravedad, masa, etc.) — EN PROGRESO
- [ ] Resolver asimetría en distribución de pesos: ¿mover atrás el bloque de inercia es realista?
