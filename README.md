# Caddy AI2 ROS2 Simulation

## Testing sdf

```bash
### 1. Corregir export
export GZ_SIM_RESOURCE_PATH='/home/racarla96/ws_ros2_caddy_dev/src/'
### 2. Procesar Xacro → SDF
cd ~/ws_ros2_caddy_dev
colcon build --packages-select bicycle_to_ackermann_steering_adapter bicycle_to_ackermann_traction_adapter caddy_ai2_ros2_gazebo_simulation
source install/setup.bash
cd ~/ws_ros2_caddy_dev/src/caddy_ai2_ros2_gazebo_simulation/description/sdf
xacro caddy_ai2_world.sdf.xacro > caddy_ai2_world.sdf
### 3. Validar SDF
gz sdf -p caddy_ai2_world.sdf > /dev/null && echo "✓ SDF válido"
### 4. Lanzar en Gazebo Sim
gz sim -v 4 -r caddy_ai2_world.sdf
```

## Simulación

```bash
colcon build --packages-select bicycle_to_ackermann_steering_adapter bicycle_to_ackermann_traction_adapter caddy_ai2_ros2_gazebo_simulation
export GZ_SIM_RESOURCE_PATH="$GZ_SIM_RESOURCE_PATH:$(ros2 pkg prefix caddy_ai2_ros2_gazebo_simulation --share)/description/meshes"
```

# Publicar un valor de posición del steering y velocidad lineal
ros2 topic pub /forward_position_command_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.3]}" -r 100
ros2 topic pub /forward_velocity_command_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.3]}" -r 100

ros2 topic pub /bicycle_steering_controller/reference geometry_msgs/msg/TwistStamped "
header:
  stamp:
    sec: 0
    nanosec: 0
  frame_id: 'base_link'
twist:
  linear:
    x: 1.0
    y: 0.0
    z: 0.0
  angular:
    x: 0.0
    y: 0.0
    z: 0.5
"

## Medidas

![Plano del vehículo](doc/img/caddy_plane.png)

![Plano del vehículo](doc/img/car_concept.jpeg)


## Apartado visual
A la hora de hacer la simulación, se tiene un archivo aproximado del chassis del vehículo. Cómo podemos ver en las siguientes imágenes, tiene un alinamiento definido con respecto a los ejes del vehículo, pero no este no tiene en cuenta el centro de masas del vehículo. Y por lo tanto, para el aspecto visual, hay que hacer un aliniamiento, teniendo en cuenta las medidas aproximadas obtenidas, a parte de considerar la escala.

![Visualización del vehículo](doc/img/chassis_stl_align_1.png)

![Visualización del vehículo](doc/img/chassis_stl_align_2.png)

![Visualización del vehículo](doc/img/chassis_stl_align_3.png)

![Visualización del vehículo](doc/img/chassis_stl_align_4.png)

Como podemos ver, el wheelbase del vehículo está a escala en mm, es decir, 16.50 mm, del modelo visual, equivale 1:100 con el real, es decir, 1650 mm o 1.65 metros.

# TODOs

- [ ] Medir los aspectos reales del vehículo, cómo el centro de gravedad, masa del vehículo, etc (EN PROGRESO). Añadir documento de como se mide esto y hacer fotos.
- [ ] Tengo dudas sobre la asimetría en la distribución de pesos del vehículo. ¿Mover atrás el bloque de la inercia es realista? ¿Cómo se puede medir esto?