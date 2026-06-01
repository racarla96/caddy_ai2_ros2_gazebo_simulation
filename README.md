# caddy_ai2_ros2_gazebo_simulation

**ROS 2:** Jazzy | **Simulador:** Gazebo Harmonic (gz-sim 8) | **Proyecto:** CERVAREC

Paquete de simulación del robot agrícola Caddy AI2 en Gazebo Harmonic. Orquesta el spawn del robot, los controladores ros2_control, el bridge Gazebo↔ROS2 y la visualización en RViz. El modelo URDF de simulación extiende via herencia Jinja2 el template base de `caddy_ai2_ros2_description`, añadiendo los plugins de Gazebo y ros2_control.

---

## Estructura

```
caddy_ai2_ros2_gazebo_simulation/
├── bringup/
│   ├── config/
│   │   ├── controllers_simulation.yaml.j2   # Controladores ros2_control (Jinja2)
│   │   └── gz_msg_bridge.yaml.j2            # Bridge Gazebo↔ROS2 con frame_id (Jinja2)
│   ├── launch/
│   │   ├── world.launch.py                  # Lanza Gazebo con el world
│   │   ├── spawn_robot.launch.py            # Spawna una instancia de robot
│   │   ├── simulation.launch.py             # World + un robot (caso por defecto)
│   │   └── multi_robot_simulation.launch.py # World + N robots
│   └── rviz/
│       └── caddy.rviz
├── description/
│   ├── model/urdf/
│   │   └── caddy_ai2_model_sim.urdf.j2  # Extiende caddy_ai2_model.urdf.j2 (Jinja2)
│   └── world/
│       ├── caddy_ai2_world.sdf          # World por defecto (plano, Madrid GPS)
│       └── baylands.sdf                 # World PX4 baylands (SF Bay Area GPS)
└── doc/img/                             # Imágenes de documentación
```

---

## Arquitectura

```
robot_params.yaml  (caddy_ai2_ros2_description)
        │
        ├─[Jinja2]──► caddy_ai2_model.urdf.j2      (base, sin plugins Gazebo)
        │                     │ {%- extends %}
        │             caddy_ai2_model_sim.urdf.j2   (sim: ros2_control + sensores)
        │
        ├─[Jinja2]──► controllers_simulation.yaml.j2
        └─[Jinja2]──► gz_msg_bridge.yaml.j2

gz_msg_bridge.yaml.j2 → ros_gz_bridge (parameter_bridge)
  ├── /imu              (gz.msgs.IMU → sensor_msgs/Imu)
  ├── /sick_lms_291/scan (gz.msgs.LaserScan → sensor_msgs/LaserScan)
  ├── /ydlidar_x4/scan  (gz.msgs.LaserScan → sensor_msgs/LaserScan)
  ├── /navsat           (gz.msgs.NavSat → sensor_msgs/NavSatFix)
  ├── /ground_truth/odometry (gz.msgs.Odometry → nav_msgs/Odometry)
  ├── /navsat/base/fix       (gz.msgs.NavSat → sensor_msgs/NavSatFix)
  ├── /navsat/front_axle/fix (gz.msgs.NavSat → sensor_msgs/NavSatFix)
  └── /navsat/rear_axle/fix  (gz.msgs.NavSat → sensor_msgs/NavSatFix)
```

### Sensores en simulación

El modelo de simulación incluye:

| Sensor | Tipo | Topic | Frecuencia |
|---|---|---|---|
| SBG IG-500N (IMU) | `imu` | `/imu` | configurable |
| SICK LMS291 (LIDAR 2D) | `gpu_lidar`/`lidar` | `/sick_lms_291/scan` | configurable |
| YDLidar X4 (LIDAR 2D) | `gpu_lidar`/`lidar` | `/ydlidar_x4/scan` | configurable |
| NavSat genérico | `navsat` | `/navsat` | configurable |
| NavSat base_footprint | `navsat` | `/navsat/base/fix` | 5 Hz |
| NavSat eje delantero | `navsat` | `/navsat/front_axle/fix` | 5 Hz |
| NavSat eje trasero | `navsat` | `/navsat/rear_axle/fix` | 5 Hz |
| Odometría ground truth | `OdometryPublisher` | `/ground_truth/odometry` | 50 Hz |

---

## Build

```bash
colcon build --packages-select caddy_ai2_ros2_gazebo_simulation
source install/setup.bash
```

---

## Uso

### Robot único (caso por defecto)

```bash
ros2 launch caddy_ai2_ros2_gazebo_simulation simulation.launch.py
```

### World alternativo (baylands)

```bash
# Primera vez: descarga modelos desde Gazebo Fuel (~100 MB, requiere internet)
ros2 launch caddy_ai2_ros2_gazebo_simulation simulation.launch.py \
  world:=baylands.sdf
```

### World externo (ruta absoluta)

```bash
ros2 launch caddy_ai2_ros2_gazebo_simulation simulation.launch.py \
  world:=/ruta/absoluta/mi_mundo.sdf \
  gz_resource_path:=/ruta/a/modelos_externos
```

### Multi-robot

```bash
# Paso 1 — lanzar el world (una sola vez)
ros2 launch caddy_ai2_ros2_gazebo_simulation world.launch.py

# Paso 2 — spawnar cada robot
ros2 launch caddy_ai2_ros2_gazebo_simulation spawn_robot.launch.py \
  robot_name:=robot1 namespace:=robot1 prefix:=robot1/ x:=0.0 y:=0.0

ros2 launch caddy_ai2_ros2_gazebo_simulation spawn_robot.launch.py \
  robot_name:=robot2 namespace:=robot2 prefix:=robot2/ x:=3.0 y:=0.0
```

### Argumentos de `simulation.launch.py`

| Argumento | Default | Descripción |
|---|---|---|
| `world` | `caddy_ai2_world.sdf` | Fichero SDF (relativo a `description/world/`) o ruta absoluta |
| `gz_resource_path` | `` | Directorio extra para `GZ_SIM_RESOURCE_PATH` |
| `robot_name` | `caddy_ai2` | Nombre del modelo en Gazebo |
| `namespace` | `` | Namespace ROS2 |
| `prefix` | `` | Prefijo de TF frames |
| `x`, `y`, `z` | `0.0` | Posición de spawn (m) |
| `yaw` | `0.0` | Orientación de spawn (rad) |

### Control manual

```bash
ros2 topic pub /bicycle_steering_controller/reference geometry_msgs/msg/TwistStamped "{
  header: {frame_id: 'base_link'},
  twist: {linear: {x: 1.0}, angular: {z: 0.3}}
}"
```

### Verificar sensores

```bash
ros2 topic list | grep -E "navsat|ground_truth|imu|scan"
ros2 topic hz /ground_truth/odometry          # debe ser ~50 Hz
ros2 topic echo /navsat/base/fix --once
```

---

## Medidas del vehículo

![Plano del vehículo](doc/img/caddy_plane.png)
