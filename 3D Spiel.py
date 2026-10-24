import json
import math
import os
from datetime import datetime

import pygame
import OpenGL.GL as gl
import OpenGL.GLU as glu


WIDTH = 2000
HEIGHT = 950

MOVE_SPEED = 5.0
MOUSE_SENSITIVITY = 0.15
PLAYER_RADIUS = 0.35

ROOM_WIDTH = 7.0
ROOM_DEPTH = 9.5
ROOM_HEIGHT = 3.0
WALL_THICKNESS = 0.2

ROOM1_MIN_X = -ROOM_WIDTH / 2
ROOM1_MAX_X = ROOM_WIDTH / 2
ROOM1_MIN_Z = -ROOM_DEPTH / 2
ROOM1_MAX_Z = ROOM_DEPTH / 2

ROOM2_MIN_X = ROOM1_MIN_X
ROOM2_MAX_X = ROOM1_MAX_X
ROOM2_MIN_Z = ROOM1_MIN_Z - ROOM_DEPTH
ROOM2_MAX_Z = ROOM1_MIN_Z

WORLD_MIN_X = -25.0
WORLD_MAX_X = 25.0
WORLD_MIN_Z = -35.0
WORLD_MAX_Z = 25.0

HOUSE_BACK_Z = ROOM2_MIN_Z

INTERNAL_PASSAGE_WIDTH = 2.6
INTERNAL_PASSAGE_HEIGHT = 2.4

EXTERIOR_DOOR_WIDTH = 1.4
EXTERIOR_DOOR_HEIGHT = 2.2
EXTERIOR_DOOR_THICKNESS = 0.12

WINDOW_X = -2.0
WINDOW_WIDTH = 2.6
WINDOW_HEIGHT = 1.6
WINDOW_BOTTOM = 1.0
WINDOW_FRAME = 0.12
WINDOW_THICKNESS = 0.05

SAVE_FILE = "savegame.json"
AUTOSAVE_INTERVAL = 10.0
MOTION_LIGHT_OFF_DELAY = 5.0

CEILING_LAMP_Y = ROOM_HEIGHT - 0.25

LOCATION_LATITUDE = 51.0
LOCATION_LONGITUDE = 10.0

SUN_DISTANCE = 45.0
MOON_DISTANCE = 42.0

STREET_LAMP_POSITIONS = [
    (-4.0, -16.0),
    (4.0, -16.0),
    (-4.0, -21.0),
    (4.0, -21.0),
    (-4.0, -26.0),
    (4.0, -26.0),
]

TREES = [
    (-14.0, -15.0, 1.3, 0),
    (-15.0, 2.0, 1.4, 2),
    (-20.0, 10.0, 1.2, 3),
    (12.0, -15.0, 1.2, 2),
    (17.0, -8.0, 1.4, 0),
    (15.0, 3.0, 1.0, 3),
    (10.0, 17.0, 1.1, 2),
    (-22.0, -22.0, 1.4, 0),
    (22.0, -22.0, 1.4, 3),
]


class Player:

    def __init__(self):
        self.x = 0.0
        self.y = 1.7
        self.z = 0.0

        self.yaw = 180.0
        self.pitch = 0.0

    def move(self, keys, delta_time, game):
        speed = MOVE_SPEED * delta_time
        yaw = math.radians(self.yaw)

        forward_x = -math.sin(yaw)
        forward_z = -math.cos(yaw)

        right_x = math.cos(yaw)
        right_z = -math.sin(yaw)

        move_x = 0.0
        move_z = 0.0

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move_x += forward_x * speed
            move_z += forward_z * speed

        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move_x -= forward_x * speed
            move_z -= forward_z * speed

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move_x -= right_x * speed
            move_z -= right_z * speed

        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move_x += right_x * speed
            move_z += right_z * speed

        new_x = self.x + move_x
        new_z = self.z + move_z

        if can_move(new_x, self.z, game):
            self.x = new_x

        if can_move(self.x, new_z, game):
            self.z = new_z

    def mouse_look(self, mouse_x, mouse_y):
        self.yaw -= mouse_x * MOUSE_SENSITIVITY
        self.pitch += mouse_y * MOUSE_SENSITIVITY

        self.pitch = max(
            -89.0,
            min(
                89.0,
                self.pitch
            )
        )

    def apply_camera(self):
        gl.glRotatef(
            self.pitch,
            1,
            0,
            0
        )

        gl.glRotatef(
            -self.yaw,
            0,
            1,
            0
        )

        gl.glTranslatef(
            -self.x,
            -self.y,
            -self.z
        )


class ExteriorDoor:

    def __init__(self):
        self.x = 0.0
        self.z = ROOM2_MIN_Z - 0.06

        self.angle = 0.0
        self.target_angle = 0.0

        self.open = False

    def toggle(self):
        self.open = not self.open
        self.target_angle = 90.0 if self.open else 0.0

    def update(self, delta_time):
        speed = 180.0 * delta_time

        if self.angle < self.target_angle:
            self.angle = min(
                self.angle + speed,
                self.target_angle
            )

        elif self.angle > self.target_angle:
            self.angle = max(
                self.angle - speed,
                self.target_angle
            )

    def is_open(self):
        return self.angle > 45.0


class Window:

    def __init__(self):
        self.x = WINDOW_X
        self.z = ROOM1_MAX_Z + 0.02

        self.left_offset = 0.0
        self.target_offset = 0.0

        self.open = False

    def toggle(self):
        self.open = not self.open

        self.target_offset = (
            WINDOW_WIDTH / 2
            if self.open
            else 0.0
        )

    def update(self, delta_time):
        speed = 2.5 * delta_time

        if self.left_offset < self.target_offset:
            self.left_offset = min(
                self.left_offset + speed,
                self.target_offset
            )

        elif self.left_offset > self.target_offset:
            self.left_offset = max(
                self.left_offset - speed,
                self.target_offset
            )


class CarryableObject:

    def __init__(
        self,
        x,
        y,
        z,
        width,
        height,
        depth,
        pickup_distance,
        name,
        hold_distance=1.5,
        place_distance=1.6
    ):
        self.x = x
        self.y = y
        self.z = z

        self.width = width
        self.height = height
        self.depth = depth

        self.pickup_distance = pickup_distance
        self.name = name

        self.hold_distance = hold_distance
        self.place_distance = place_distance

        self.held = False

    def is_near(self, player):
        if self.held:
            return False

        return distance_2d(
            player.x,
            player.z,
            self.x,
            self.z
        ) < self.pickup_distance

    def pick_up(self):
        self.held = True

    def put_down(self, player):
        self.x, self.z = position_in_front_of_player(
            player,
            self.place_distance
        )

        self.held = False

    def update_held_position(self, player):
        if not self.held:
            return

        self.x, self.z = position_in_front_of_player(
            player,
            self.hold_distance
        )


class Bed(CarryableObject):

    def __init__(self):
        super().__init__(
            x=0.0,
            y=0.35,
            z=2.8,
            width=2.0,
            height=0.5,
            depth=3.5,
            pickup_distance=2.2,
            name="Bett"
        )


class Nightstand(CarryableObject):

    def __init__(self):
        super().__init__(
            x=1.4,
            y=0.45,
            z=4.45,
            width=0.9,
            height=0.9,
            depth=0.8,
            pickup_distance=1.5,
            name="Nachttisch"
        )


class Table(CarryableObject):

    def __init__(self):
        super().__init__(
            x=0.0,
            y=0.85,
            z=-9.0,
            width=1.8,
            height=1.0,
            depth=1.0,
            pickup_distance=2.0,
            name="Tisch"
        )


class Chair(CarryableObject):

    def __init__(self, x, z, rotation=0.0):
        super().__init__(
            x=x,
            y=0.45,
            z=z,
            width=0.9,
            height=1.35,
            depth=0.9,
            pickup_distance=1.5,
            name="Stuhl"
        )

        self.rotation = rotation


class NightstandLamp:

    def __init__(self):
        self.x = 1.4
        self.z = 4.45

        self.base_y = 0.95
        self.light_y = 1.65

        self.is_on = True
        self.held = False

    def is_near(self, player):
        if self.held:
            return False

        return distance_2d(
            player.x,
            player.z,
            self.x,
            self.z
        ) < 2.0

    def pick_up(self):
        self.held = True

    def put_down(self, player):
        self.x, self.z = position_in_front_of_player(
            player,
            1.6
        )

        self.base_y = 0.95
        self.light_y = 1.65

        self.held = False

    def update_held_position(self, player):
        if not self.held:
            return

        self.x, self.z = position_in_front_of_player(
            player,
            1.25
        )

        self.base_y = 1.25
        self.light_y = 1.95


class CeilingLamp:

    def __init__(self, x=0.0, z=0.0):
        self.x = x
        self.y = CEILING_LAMP_Y
        self.z = z

        self.is_on = True


class StreetLamp:

    def __init__(self, x, z):
        self.x = x
        self.z = z

    def draw(self, is_night):
        draw_cube(
            self.x,
            1.5,
            self.z,
            0.12,
            3.0,
            0.12,
            0.08,
            0.08,
            0.08
        )

        draw_cube(
            self.x,
            3.0,
            self.z,
            0.65,
            0.12,
            0.65,
            0.08,
            0.08,
            0.08
        )

        bulb_color = (
            (1.0, 0.82, 0.35)
            if is_night
            else (0.18, 0.18, 0.16)
        )

        draw_cube(
            self.x,
            2.85,
            self.z,
            0.42,
            0.22,
            0.42,
            *bulb_color
        )


STREET_LAMPS = [
    StreetLamp(x, z)
    for x, z in STREET_LAMP_POSITIONS
]


def distance_2d(x1, z1, x2, z2):
    return math.hypot(
        x1 - x2,
        z1 - z2
    )


def position_in_front_of_player(player, distance):
    yaw = math.radians(player.yaw)

    forward_x = -math.sin(yaw)
    forward_z = -math.cos(yaw)

    return (
        player.x + forward_x * distance,
        player.z + forward_z * distance
    )


def point_inside_box(
    x,
    z,
    box_x,
    box_z,
    width,
    depth,
    radius
):
    min_x = box_x - width / 2 - radius
    max_x = box_x + width / 2 + radius

    min_z = box_z - depth / 2 - radius
    max_z = box_z + depth / 2 + radius

    return (
        min_x <= x <= max_x
        and min_z <= z <= max_z
    )


def inside_room1(x, z):
    margin = PLAYER_RADIUS

    return (
        ROOM1_MIN_X + margin <= x <= ROOM1_MAX_X - margin
        and ROOM1_MIN_Z + margin <= z <= ROOM1_MAX_Z - margin
    )


def inside_room2(x, z):
    margin = PLAYER_RADIUS

    return (
        ROOM2_MIN_X + margin <= x <= ROOM2_MAX_X - margin
        and ROOM2_MIN_Z + margin <= z <= ROOM2_MAX_Z - margin
    )


def inside_exterior_doorway(x, z):
    doorway_width = (
        EXTERIOR_DOOR_WIDTH / 2
        + PLAYER_RADIUS
    )

    doorway_depth = PLAYER_RADIUS + 0.20

    return (
        abs(x) <= doorway_width
        and abs(z - HOUSE_BACK_Z) <= doorway_depth
    )


def inside_world(x, z):
    margin = PLAYER_RADIUS

    return (
        WORLD_MIN_X + margin <= x <= WORLD_MAX_X - margin
        and WORLD_MIN_Z + margin <= z <= WORLD_MAX_Z - margin
    )


def collides_with_tree(x, z):
    for tree_x, tree_z, scale, _ in TREES:
        radius = 0.65 * scale

        if distance_2d(
            x,
            z,
            tree_x,
            tree_z
        ) < radius + PLAYER_RADIUS:
            return True

    return False


def outside_house_collision(x, z):
    return (
        ROOM1_MIN_X - PLAYER_RADIUS
        <= x
        <= ROOM1_MAX_X + PLAYER_RADIUS
        and
        HOUSE_BACK_Z - PLAYER_RADIUS
        <= z
        <= ROOM1_MAX_Z + PLAYER_RADIUS
    )


def object_collision_in_room1(x, z, game):
    for obj in (
        game.bed,
        game.nightstand
    ):
        if obj.held:
            continue

        if point_inside_box(
            x,
            z,
            obj.x,
            obj.z,
            obj.width,
            obj.depth,
            PLAYER_RADIUS
        ):
            return True

    return False


def object_collision_in_room2(x, z, game):
    if not game.table.held:

        if point_inside_box(
            x,
            z,
            game.table.x,
            game.table.z,
            game.table.width,
            game.table.depth,
            PLAYER_RADIUS
        ):
            return True

    for chair in game.chairs:

        if chair.held:
            continue

        if point_inside_box(
            x,
            z,
            chair.x,
            chair.z,
            chair.width,
            chair.depth,
            PLAYER_RADIUS
        ):
            return True

    return False


def can_move(x, z, game):
    if not inside_world(x, z):
        return False

    passage_half_width = (
        INTERNAL_PASSAGE_WIDTH / 2
        + PLAYER_RADIUS
    )

    passage_depth = PLAYER_RADIUS + 0.50

    if (
        abs(x) <= passage_half_width
        and
        abs(z - ROOM1_MIN_Z) <= passage_depth
    ):
        return True

    if inside_room1(x, z):
        return not object_collision_in_room1(
            x,
            z,
            game
        )

    if inside_room2(x, z):
        return not object_collision_in_room2(
            x,
            z,
            game
        )

    if inside_exterior_doorway(x, z):
        return game.exterior_door.is_open()

    if outside_house_collision(x, z):
        return False

    return not collides_with_tree(x, z)


def can_interact_with_exterior_door(player):
    return distance_2d(
        player.x,
        player.z,
        0.0,
        HOUSE_BACK_Z
    ) < 2.5


def can_interact_with_window(player, window):
    return distance_2d(
        player.x,
        player.z,
        window.x,
        ROOM1_MAX_Z
    ) < 2.5


def get_current_room(player):
    if inside_room2(player.x, player.z):
        return "Raum 2"

    if inside_room1(player.x, player.z):
        return "Raum 1"

    return "Außenwelt"


def julian_day(date_time):
    year = date_time.year
    month = date_time.month
    day = date_time.day

    hour = (
        date_time.hour
        + date_time.minute / 60.0
        + date_time.second / 3600.0
    )

    if month <= 2:
        year -= 1
        month += 12

    a = math.floor(year / 100)

    b = (
        2
        - a
        + math.floor(a / 4)
    )

    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
        + hour / 24.0
    )


def solar_position(date_time):
    jd = julian_day(date_time)
    n = jd - 2451545.0

    mean_longitude = (
        280.460
        + 0.9856474 * n
    ) % 360.0

    mean_anomaly = math.radians(
        (
            357.528
            + 0.9856003 * n
        ) % 360.0
    )

    ecliptic_longitude = math.radians(
        (
            mean_longitude
            + 1.915 * math.sin(mean_anomaly)
            + 0.020 * math.sin(2 * mean_anomaly)
        ) % 360.0
    )

    obliquity = math.radians(
        23.439
        - 0.0000004 * n
    )

    declination = math.asin(
        math.sin(obliquity)
        * math.sin(ecliptic_longitude)
    )

    right_ascension = math.atan2(
        math.cos(obliquity)
        * math.sin(ecliptic_longitude),
        math.cos(ecliptic_longitude)
    )

    right_ascension_hours = (
        math.degrees(right_ascension)
        / 15.0
    ) % 24.0

    gmst = (
        18.697374558
        + 24.06570982441908 * n
    ) % 24.0

    local_sidereal_time = (
        gmst
        + LOCATION_LONGITUDE / 15.0
    ) % 24.0

    hour_angle = math.radians(
        (
            local_sidereal_time
            - right_ascension_hours
        ) * 15.0
    )

    latitude = math.radians(
        LOCATION_LATITUDE
    )

    altitude = math.asin(
        math.sin(latitude)
        * math.sin(declination)
        +
        math.cos(latitude)
        * math.cos(declination)
        * math.cos(hour_angle)
    )

    azimuth = math.atan2(
        math.sin(hour_angle),
        (
            math.cos(hour_angle)
            * math.sin(latitude)
            -
            math.tan(declination)
            * math.cos(latitude)
        )
    )

    return (
        math.degrees(altitude),
        (
            math.degrees(azimuth)
            + 180.0
        ) % 360.0
    )


def moon_phase(date_time):
    known_new_moon = datetime(
        2000,
        1,
        6,
        18,
        14
    )

    days = (
        date_time - known_new_moon
    ).total_seconds() / 86400.0

    return (
        days % 29.53058867
    ) / 29.53058867


def moon_position(date_time):
    phase = moon_phase(date_time)

    solar_altitude, solar_azimuth = solar_position(
        date_time
    )

    phase_angle = phase * 360.0

    moon_elongation = (
        phase_angle - 180.0
    )

    moon_altitude = (
        -solar_altitude * 0.75
        +
        35.0
        * math.sin(
            math.radians(
                moon_elongation
            )
        )
    )

    moon_altitude = max(
        -10.0,
        min(
            80.0,
            moon_altitude
        )
    )

    moon_azimuth = (
        solar_azimuth
        + 180.0
        +
        25.0
        * math.sin(
            math.radians(
                phase_angle
            )
        )
    ) % 360.0

    return (
        moon_altitude,
        moon_azimuth,
        phase
    )


def get_sky_state(date_time):
    sun_altitude, sun_azimuth = solar_position(
        date_time
    )

    moon_altitude, moon_azimuth, phase = moon_position(
        date_time
    )

    daylight = max(
        0.0,
        min(
            1.0,
            sun_altitude / 25.0
        )
    )

    twilight = max(
        0.0,
        min(
            1.0,
            (
                sun_altitude + 12.0
            ) / 18.0
        )
    )

    return {
        "sun_altitude": sun_altitude,
        "sun_azimuth": sun_azimuth,
        "moon_altitude": moon_altitude,
        "moon_azimuth": moon_azimuth,
        "moon_phase": phase,
        "daylight": daylight,
        "twilight": twilight,
        "is_night": sun_altitude < -6.0
    }


def moon_phase_name(phase):
    if phase < 0.03:
        return "Neumond"

    if phase < 0.22:
        return "Zunehmende Sichel"

    if phase < 0.28:
        return "Erstes Viertel"

    if phase < 0.47:
        return "Zunehmender Mond"

    if phase < 0.53:
        return "Vollmond"

    if phase < 0.72:
        return "Abnehmender Mond"

    if phase < 0.78:
        return "Letztes Viertel"

    return "Abnehmende Sichel"


def celestial_position(
    altitude,
    azimuth,
    distance
):
    altitude_rad = math.radians(
        altitude
    )

    azimuth_rad = math.radians(
        azimuth
    )

    return (
        distance
        * math.cos(altitude_rad)
        * math.sin(azimuth_rad),

        distance
        * math.sin(altitude_rad),

        -distance
        * math.cos(altitude_rad)
        * math.cos(azimuth_rad)
    )


def update_sky(sky):
    daylight = sky["daylight"]
    twilight = sky["twilight"]
    altitude = sky["sun_altitude"]

    if altitude >= 0:

        red = (
            0.18
            + 0.27 * daylight
        )

        green = (
            0.28
            + 0.37 * daylight
        )

        blue = (
            0.45
            + 0.45 * daylight
        )

    elif altitude >= -6:

        red = (
            0.08
            + 0.18 * twilight
        )

        green = (
            0.10
            + 0.25 * twilight
        )

        blue = (
            0.25
            + 0.45 * twilight
        )

    else:
        red = 0.008
        green = 0.012
        blue = 0.045

    gl.glClearColor(
        red,
        green,
        blue,
        1.0
    )


def update_sun_light(sky):
    altitude = sky["sun_altitude"]

    if altitude <= -6.0:
        gl.glDisable(
            gl.GL_LIGHT4
        )
        return

    gl.glEnable(
        gl.GL_LIGHT4
    )

    position = celestial_position(
        altitude,
        sky["sun_azimuth"],
        SUN_DISTANCE
    )

    intensity = max(
        0.08,
        min(
            1.0,
            (
                altitude + 6.0
            ) / 30.0
        )
    )

    gl.glLightfv(
        gl.GL_LIGHT4,
        gl.GL_POSITION,
        [
            position[0],
            position[1],
            position[2],
            0.0
        ]
    )

    gl.glLightfv(
        gl.GL_LIGHT4,
        gl.GL_DIFFUSE,
        [
            intensity,
            0.90 * intensity,
            0.70 * intensity,
            1.0
        ]
    )

    gl.glLightfv(
        gl.GL_LIGHT4,
        gl.GL_SPECULAR,
        [
            intensity,
            0.90 * intensity,
            0.70 * intensity,
            1.0
        ]
    )

    gl.glLightf(
        gl.GL_LIGHT4,
        gl.GL_CONSTANT_ATTENUATION,
        1.0
    )


def update_moon_light(sky):
    altitude = sky["moon_altitude"]
    phase = sky["moon_phase"]

    illuminated = (
        1.0
        -
        abs(
            2.0 * phase - 1.0
        )
    )

    if (
        altitude <= 0
        or illuminated < 0.05
    ):
        gl.glDisable(
            gl.GL_LIGHT5
        )
        return

    gl.glEnable(
        gl.GL_LIGHT5
    )

    position = celestial_position(
        altitude,
        sky["moon_azimuth"],
        MOON_DISTANCE
    )

    moon_strength = (
        0.08
        + 0.18 * illuminated
    )

    gl.glLightfv(
        gl.GL_LIGHT5,
        gl.GL_POSITION,
        [
            position[0],
            position[1],
            position[2],
            0.0
        ]
    )

    gl.glLightfv(
        gl.GL_LIGHT5,
        gl.GL_DIFFUSE,
        [
            moon_strength,
            moon_strength,
            moon_strength * 1.15,
            1.0
        ]
    )

    gl.glLightfv(
        gl.GL_LIGHT5,
        gl.GL_SPECULAR,
        [
            moon_strength,
            moon_strength,
            moon_strength,
            1.0
        ]
    )

    gl.glLightf(
        gl.GL_LIGHT5,
        gl.GL_CONSTANT_ATTENUATION,
        1.0
    )


def draw_sphere(
    x,
    y,
    z,
    radius,
    red,
    green,
    blue,
    segments=32,
    rings=20
):
    gl.glPushMatrix()

    gl.glTranslatef(
        x,
        y,
        z
    )

    gl.glColor3f(
        red,
        green,
        blue
    )

    quadric = glu.gluNewQuadric()

    glu.gluSphere(
        quadric,
        radius,
        segments,
        rings
    )

    glu.gluDeleteQuadric(
        quadric
    )

    gl.glPopMatrix()


def draw_sun(sky):
    altitude = sky["sun_altitude"]

    if altitude < -6:
        return

    position = celestial_position(
        altitude,
        sky["sun_azimuth"],
        SUN_DISTANCE
    )

    gl.glDisable(
        gl.GL_LIGHTING
    )

    draw_sphere(
        position[0],
        position[1],
        position[2],
        1.7,
        1.0,
        0.75,
        0.15,
        32,
        20
    )

    gl.glEnable(
        gl.GL_LIGHTING
    )


def draw_moon(sky):
    altitude = sky["moon_altitude"]

    if altitude <= -5:
        return

    phase = sky["moon_phase"]

    illuminated = (
        1.0
        -
        abs(
            2.0 * phase - 1.0
        )
    )

    if illuminated < 0.03:
        return

    position = celestial_position(
        altitude,
        sky["moon_azimuth"],
        MOON_DISTANCE
    )

    brightness = (
        0.45
        + 0.55 * illuminated
    )

    gl.glDisable(
        gl.GL_LIGHTING
    )

    draw_sphere(
        position[0],
        position[1],
        position[2],
        1.3,
        brightness,
        brightness,
        brightness,
        32,
        20
    )

    gl.glEnable(
        gl.GL_LIGHTING
    )


def draw_cube(
    x,
    y,
    z,
    width,
    height,
    depth,
    red,
    green,
    blue
):
    half_width = width / 2
    half_height = height / 2
    half_depth = depth / 2

    vertices = [
        (
            -half_width,
            -half_height,
            -half_depth
        ),
        (
            half_width,
            -half_height,
            -half_depth
        ),
        (
            half_width,
            half_height,
            -half_depth
        ),
        (
            -half_width,
            half_height,
            -half_depth
        ),
        (
            -half_width,
            -half_height,
            half_depth
        ),
        (
            half_width,
            -half_height,
            half_depth
        ),
        (
            half_width,
            half_height,
            half_depth
        ),
        (
            -half_width,
            half_height,
            half_depth
        )
    ]

    faces = (
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 4, 7, 3),
        (1, 5, 6, 2),
        (3, 2, 6, 7),
        (0, 1, 5, 4)
    )

    gl.glPushMatrix()

    gl.glTranslatef(
        x,
        y,
        z
    )

    gl.glColor3f(
        red,
        green,
        blue
    )

    gl.glBegin(
        gl.GL_QUADS
    )

    for face in faces:
        for vertex in face:
            gl.glVertex3fv(
                vertices[vertex]
            )

    gl.glEnd()

    gl.glPopMatrix()


def draw_world():
    draw_cube(
        0,
        -0.12,
        -5.0,
        50.0,
        0.2,
        60.0,
        0.18,
        0.42,
        0.16
    )

    draw_cube(
        0,
        0.01,
        19.0,
        46.0,
        0.04,
        3.5,
        0.12,
        0.12,
        0.12
    )

    draw_cube(
        0,
        0.03,
        11.0,
        2.0,
        0.04,
        12.0,
        0.48,
        0.38,
        0.25
    )

    for tree in TREES:
        draw_tree(tree)


def draw_tree(tree):
    x, z, scale, tree_type = tree

    trunk_height = 2.0 * scale
    trunk_width = 0.45 * scale

    draw_cube(
        x,
        trunk_height / 2,
        z,
        trunk_width,
        trunk_height,
        trunk_width,
        0.30,
        0.16,
        0.07
    )

    if tree_type == 0:
        draw_tree_type_0(
            x,
            z,
            scale,
            trunk_height
        )

    elif tree_type == 2:
        draw_tree_type_2(
            x,
            z,
            scale,
            trunk_height
        )

    else:
        draw_tree_type_3(
            x,
            z,
            scale,
            trunk_height
        )


def draw_tree_type_0(
    x,
    z,
    scale,
    trunk_height
):
    draw_sphere(
        x,
        trunk_height + 0.9 * scale,
        z,
        1.25 * scale,
        0.07,
        0.34,
        0.08,
        24,
        16
    )

    draw_sphere(
        x - 0.75 * scale,
        trunk_height + 0.85 * scale,
        z + 0.15 * scale,
        0.82 * scale,
        0.08,
        0.39,
        0.09,
        24,
        16
    )

    draw_sphere(
        x + 0.72 * scale,
        trunk_height + 0.95 * scale,
        z - 0.10 * scale,
        0.85 * scale,
        0.09,
        0.42,
        0.10,
        24,
        16
    )


def draw_tree_type_2(
    x,
    z,
    scale,
    trunk_height
):
    draw_sphere(
        x,
        trunk_height + 0.9 * scale,
        z,
        0.95 * scale,
        0.06,
        0.30,
        0.07,
        24,
        16
    )

    draw_sphere(
        x,
        trunk_height + 1.85 * scale,
        z,
        1.05 * scale,
        0.08,
        0.38,
        0.09,
        24,
        16
    )

    draw_sphere(
        x - 0.30 * scale,
        trunk_height + 2.65 * scale,
        z + 0.05 * scale,
        0.80 * scale,
        0.10,
        0.44,
        0.10,
        24,
        16
    )


def draw_tree_type_3(
    x,
    z,
    scale,
    trunk_height
):
    draw_sphere(
        x,
        trunk_height + 1.0 * scale,
        z,
        1.0 * scale,
        0.07,
        0.36,
        0.08,
        24,
        16
    )

    draw_sphere(
        x - 0.9 * scale,
        trunk_height + 1.15 * scale,
        z,
        0.85 * scale,
        0.06,
        0.32,
        0.07,
        24,
        16
    )

    draw_sphere(
        x + 0.9 * scale,
        trunk_height + 1.15 * scale,
        z + 0.05 * scale,
        0.85 * scale,
        0.08,
        0.40,
        0.09,
        24,
        16
    )

    draw_sphere(
        x,
        trunk_height + 1.85 * scale,
        z,
        0.72 * scale,
        0.10,
        0.46,
        0.11,
        24,
        16
    )


def draw_room_floor(center_z):
    draw_cube(
        0,
        -0.1,
        center_z,
        ROOM_WIDTH,
        0.2,
        ROOM_DEPTH,
        0.25,
        0.25,
        0.25
    )


def draw_room_ceiling(center_z):
    draw_cube(
        0,
        ROOM_HEIGHT,
        center_z,
        ROOM_WIDTH,
        0.2,
        ROOM_DEPTH,
        0.35,
        0.35,
        0.35
    )


def draw_room1_walls():
    wall_color = (
        0.55,
        0.85,
        0.70
    )

    dark_green = (
        0.06,
        0.32,
        0.14
    )

    side_width = (
        ROOM_WIDTH
        - INTERNAL_PASSAGE_WIDTH
    ) / 2

    left_x = -(
        INTERNAL_PASSAGE_WIDTH / 2
        + side_width / 2
    )

    right_x = (
        INTERNAL_PASSAGE_WIDTH / 2
        + side_width / 2
    )

    draw_cube(
        left_x,
        ROOM_HEIGHT / 2,
        ROOM1_MIN_Z,
        side_width,
        ROOM_HEIGHT,
        WALL_THICKNESS,
        *dark_green
    )

    draw_cube(
        right_x,
        ROOM_HEIGHT / 2,
        ROOM1_MIN_Z,
        side_width,
        ROOM_HEIGHT,
        WALL_THICKNESS,
        *dark_green
    )

    top_height = (
        ROOM_HEIGHT
        - INTERNAL_PASSAGE_HEIGHT
    )

    draw_cube(
        0,
        INTERNAL_PASSAGE_HEIGHT
        + top_height / 2,
        ROOM1_MIN_Z,
        INTERNAL_PASSAGE_WIDTH,
        top_height,
        WALL_THICKNESS,
        *dark_green
    )

    draw_cube(
        ROOM1_MIN_X,
        ROOM_HEIGHT / 2,
        0,
        WALL_THICKNESS,
        ROOM_HEIGHT,
        ROOM_DEPTH,
        *wall_color
    )

    draw_cube(
        ROOM1_MAX_X,
        ROOM_HEIGHT / 2,
        0,
        WALL_THICKNESS,
        ROOM_HEIGHT,
        ROOM_DEPTH,
        *wall_color
    )

    draw_back_wall_with_window(
        dark_green
    )


def draw_back_wall_with_window(
    wall_color
):
    wall_z = ROOM1_MAX_Z

    window_left = (
        WINDOW_X
        - WINDOW_WIDTH / 2
    )

    window_right = (
        WINDOW_X
        + WINDOW_WIDTH / 2
    )

    left_width = (
        window_left
        - ROOM1_MIN_X
    )

    right_width = (
        ROOM1_MAX_X
        - window_right
    )

    draw_cube(
        ROOM1_MIN_X + left_width / 2,
        ROOM_HEIGHT / 2,
        wall_z,
        left_width,
        ROOM_HEIGHT,
        WALL_THICKNESS,
        *wall_color
    )

    draw_cube(
        ROOM1_MAX_X - right_width / 2,
        ROOM_HEIGHT / 2,
        wall_z,
        right_width,
        ROOM_HEIGHT,
        WALL_THICKNESS,
        *wall_color
    )

    draw_cube(
        WINDOW_X,
        WINDOW_BOTTOM / 2,
        wall_z,
        WINDOW_WIDTH,
        WINDOW_BOTTOM,
        WALL_THICKNESS,
        *wall_color
    )

    window_top = (
        WINDOW_BOTTOM
        + WINDOW_HEIGHT
    )

    top_height = (
        ROOM_HEIGHT
        - window_top
    )

    draw_cube(
        WINDOW_X,
        window_top + top_height / 2,
        wall_z,
        WINDOW_WIDTH,
        top_height,
        WALL_THICKNESS,
        *wall_color
    )

    draw_window_frame(
        wall_z
    )


def draw_room2_walls():
    wall_color = (
        0.48,
        0.50,
        0.53
    )

    center_z = (
        ROOM2_MIN_Z
        + ROOM2_MAX_Z
    ) / 2

    room_depth = (
        ROOM2_MAX_Z
        - ROOM2_MIN_Z
    )

    draw_cube(
        ROOM2_MIN_X,
        ROOM_HEIGHT / 2,
        center_z,
        WALL_THICKNESS,
        ROOM_HEIGHT,
        room_depth,
        *wall_color
    )

    draw_cube(
        ROOM2_MAX_X,
        ROOM_HEIGHT / 2,
        center_z,
        WALL_THICKNESS,
        ROOM_HEIGHT,
        room_depth,
        *wall_color
    )

    draw_exterior_back_wall(
        wall_color
    )


def draw_exterior_back_wall(
    wall_color
):
    wall_z = ROOM2_MIN_Z

    side_width = (
        ROOM_WIDTH
        - EXTERIOR_DOOR_WIDTH
    ) / 2

    left_x = -(
        EXTERIOR_DOOR_WIDTH / 2
        + side_width / 2
    )

    right_x = (
        EXTERIOR_DOOR_WIDTH / 2
        + side_width / 2
    )

    draw_cube(
        left_x,
        ROOM_HEIGHT / 2,
        wall_z,
        side_width,
        ROOM_HEIGHT,
        WALL_THICKNESS,
        *wall_color
    )

    draw_cube(
        right_x,
        ROOM_HEIGHT / 2,
        wall_z,
        side_width,
        ROOM_HEIGHT,
        WALL_THICKNESS,
        *wall_color
    )

    top_height = (
        ROOM_HEIGHT
        - EXTERIOR_DOOR_HEIGHT
    )

    draw_cube(
        0,
        EXTERIOR_DOOR_HEIGHT
        + top_height / 2,
        wall_z,
        EXTERIOR_DOOR_WIDTH,
        top_height,
        WALL_THICKNESS,
        *wall_color
    )


def draw_window_frame(wall_z):
    glass_y = (
        WINDOW_BOTTOM
        + WINDOW_HEIGHT / 2
    )

    frame_color = (
        0.12,
        0.07,
        0.04
    )

    glass_color = (
        0.20,
        0.45,
        0.65
    )

    draw_cube(
        WINDOW_X,
        glass_y,
        wall_z - 0.04,
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        0.04,
        *glass_color
    )

    draw_cube(
        WINDOW_X - WINDOW_WIDTH / 2,
        glass_y,
        wall_z - 0.08,
        WINDOW_FRAME,
        WINDOW_HEIGHT + WINDOW_FRAME * 2,
        0.14,
        *frame_color
    )

    draw_cube(
        WINDOW_X + WINDOW_WIDTH / 2,
        glass_y,
        wall_z - 0.08,
        WINDOW_FRAME,
        WINDOW_HEIGHT + WINDOW_FRAME * 2,
        0.14,
        *frame_color
    )

    draw_cube(
        WINDOW_X,
        WINDOW_BOTTOM,
        wall_z - 0.08,
        WINDOW_WIDTH,
        WINDOW_FRAME,
        0.14,
        *frame_color
    )

    draw_cube(
        WINDOW_X,
        WINDOW_BOTTOM + WINDOW_HEIGHT,
        wall_z - 0.08,
        WINDOW_WIDTH,
        WINDOW_FRAME,
        0.14,
        *frame_color
    )

    draw_cube(
        WINDOW_X,
        glass_y,
        wall_z - 0.08,
        WINDOW_FRAME,
        WINDOW_HEIGHT,
        0.14,
        *frame_color
    )


def draw_window(window):
    wall_z = window.z

    glass_y = (
        WINDOW_BOTTOM
        + WINDOW_HEIGHT / 2
    )

    frame_color = (
        0.12,
        0.07,
        0.04
    )

    glass_color = (
        0.20,
        0.45,
        0.65
    )

    half_width = (
        WINDOW_WIDTH / 2
    )

    draw_cube(
        window.x + half_width / 2,
        glass_y,
        wall_z - 0.05,
        half_width,
        WINDOW_HEIGHT,
        WINDOW_THICKNESS,
        *glass_color
    )

    left_x = (
        window.x
        - half_width / 2
        + window.left_offset
    )

    draw_cube(
        left_x,
        glass_y,
        wall_z - 0.07,
        half_width,
        WINDOW_HEIGHT,
        WINDOW_THICKNESS,
        *glass_color
    )

    draw_cube(
        window.x - WINDOW_WIDTH / 2,
        glass_y,
        wall_z - 0.09,
        WINDOW_FRAME,
        WINDOW_HEIGHT + WINDOW_FRAME * 2,
        0.14,
        *frame_color
    )

    draw_cube(
        window.x + WINDOW_WIDTH / 2,
        glass_y,
        wall_z - 0.09,
        WINDOW_FRAME,
        WINDOW_HEIGHT + WINDOW_FRAME * 2,
        0.14,
        *frame_color
    )

    draw_cube(
        window.x,
        WINDOW_BOTTOM,
        wall_z - 0.09,
        WINDOW_WIDTH,
        WINDOW_FRAME,
        0.14,
        *frame_color
    )

    draw_cube(
        window.x,
        WINDOW_BOTTOM + WINDOW_HEIGHT,
        wall_z - 0.09,
        WINDOW_WIDTH,
        WINDOW_FRAME,
        0.14,
        *frame_color
    )

    draw_cube(
        window.x,
        glass_y,
        wall_z - 0.09,
        WINDOW_FRAME,
        WINDOW_HEIGHT,
        0.14,
        *frame_color
    )


def draw_exterior_door(door):
    gl.glPushMatrix()

    gl.glTranslatef(
        door.x - EXTERIOR_DOOR_WIDTH / 2,
        EXTERIOR_DOOR_HEIGHT / 2,
        door.z
    )

    gl.glRotatef(
        -door.angle,
        0,
        1,
        0
    )

    gl.glTranslatef(
        EXTERIOR_DOOR_WIDTH / 2,
        0,
        0
    )

    draw_cube(
        0,
        0,
        0,
        EXTERIOR_DOOR_WIDTH,
        EXTERIOR_DOOR_HEIGHT,
        EXTERIOR_DOOR_THICKNESS,
        0.25,
        0.12,
        0.05
    )

    draw_cube(
        0.43,
        0.0,
        -0.09,
        0.16,
        0.16,
        0.06,
        0.08,
        0.08,
        0.08
    )

    draw_cube(
        0.43,
        0.0,
        -0.15,
        0.12,
        0.12,
        0.10,
        0.08,
        0.08,
        0.08
    )

    draw_cube(
        0.43,
        0.0,
        0.09,
        0.16,
        0.16,
        0.06,
        0.08,
        0.08,
        0.08
    )

    draw_cube(
        0.43,
        0.0,
        0.15,
        0.12,
        0.12,
        0.10,
        0.08,
        0.08,
        0.08
    )

    gl.glPopMatrix()


def draw_bed(bed):
    if bed.held:

        draw_cube(
            bed.x,
            0.35,
            bed.z,
            bed.width,
            0.5,
            bed.depth,
            0.25,
            0.15,
            0.08
        )

        draw_cube(
            bed.x,
            0.70,
            bed.z,
            bed.width - 0.1,
            0.25,
            bed.depth - 0.1,
            0.75,
            0.75,
            0.78
        )

        draw_cube(
            bed.x,
            0.90,
            bed.z + 1.1,
            bed.width - 0.2,
            0.2,
            0.9,
            0.85,
            0.85,
            0.9
        )

        return

    draw_cube(
        bed.x,
        bed.y,
        bed.z,
        bed.width,
        bed.height,
        bed.depth,
        0.25,
        0.15,
        0.08
    )

    draw_cube(
        bed.x,
        bed.y + 0.35,
        bed.z,
        bed.width - 0.1,
        0.25,
        bed.depth - 0.1,
        0.75,
        0.75,
        0.78
    )

    draw_cube(
        bed.x,
        bed.y + 0.55,
        bed.z + 1.1,
        bed.width - 0.2,
        0.2,
        0.9,
        0.85,
        0.85,
        0.9
    )


def draw_nightstand(nightstand):
    draw_cube(
        nightstand.x,
        nightstand.y,
        nightstand.z,
        nightstand.width,
        nightstand.height,
        nightstand.depth,
        0.28,
        0.16,
        0.08
    )


def draw_table(table):
    draw_cube(
        table.x,
        table.y,
        table.z,
        table.width,
        0.15,
        table.depth,
        0.42,
        0.22,
        0.08
    )

    leg_y = 0.425

    for x_offset in (
        -0.65,
        0.65
    ):
        for z_offset in (
            -0.35,
            0.35
        ):
            draw_cube(
                table.x + x_offset,
                leg_y,
                table.z + z_offset,
                0.12,
                0.85,
                0.12,
                0.25,
                0.12,
                0.04
            )


def draw_chair(chair):
    gl.glPushMatrix()

    gl.glTranslatef(
        chair.x,
        0,
        chair.z
    )

    gl.glRotatef(
        chair.rotation,
        0,
        1,
        0
    )

    wood_dark = (
        0.25,
        0.12,
        0.05
    )

    wood = (
        0.38,
        0.20,
        0.08
    )

    draw_cube(
        0,
        0.48,
        0,
        0.9,
        0.16,
        0.9,
        *wood
    )

    for x_offset in (
        -0.32,
        0.32
    ):
        for z_offset in (
            -0.32,
            0.32
        ):
            draw_cube(
                x_offset,
                0.24,
                z_offset,
                0.12,
                0.48,
                0.12,
                *wood_dark
            )

    draw_cube(
        0,
        1.05,
        0.36,
        0.9,
        1.05,
        0.14,
        *wood
    )

    draw_cube(
        0,
        0.72,
        0.36,
        0.9,
        0.10,
        0.14,
        *wood_dark
    )

    gl.glPopMatrix()


def draw_nightstand_lamp(lamp):
    draw_cube(
        lamp.x,
        lamp.base_y,
        lamp.z,
        0.35,
        0.08,
        0.35,
        0.15,
        0.15,
        0.15
    )

    draw_cube(
        lamp.x,
        lamp.base_y + 0.30,
        lamp.z,
        0.08,
        0.55,
        0.08,
        0.12,
        0.12,
        0.12
    )

    bulb_color = (
        (1.0, 0.85, 0.35)
        if lamp.is_on
        else (0.25, 0.22, 0.15)
    )

    draw_cube(
        lamp.x,
        lamp.light_y,
        lamp.z,
        0.45,
        0.35,
        0.45,
        *bulb_color
    )


def draw_ceiling_lamp(lamp):
    lamp_color = (
        (1.0, 0.85, 0.35)
        if lamp.is_on
        else (0.20, 0.20, 0.18)
    )

    draw_cube(
        lamp.x,
        lamp.y,
        lamp.z,
        0.45,
        0.12,
        0.45,
        0.15,
        0.15,
        0.15
    )

    draw_cube(
        lamp.x,
        lamp.y - 0.15,
        lamp.z,
        0.32,
        0.20,
        0.32,
        *lamp_color
    )


def setup_ceiling_light(
    lamp,
    light_id
):
    if not lamp.is_on:
        gl.glDisable(
            light_id
        )
        return

    gl.glEnable(
        light_id
    )

    gl.glLightfv(
        light_id,
        gl.GL_POSITION,
        [
            lamp.x,
            lamp.y - 0.2,
            lamp.z,
            1.0
        ]
    )

    gl.glLightfv(
        light_id,
        gl.GL_DIFFUSE,
        [
            1.0,
            0.85,
            0.55,
            1.0
        ]
    )

    gl.glLightfv(
        light_id,
        gl.GL_SPECULAR,
        [
            1.0,
            0.85,
            0.55,
            1.0
        ]
    )

    gl.glLightf(
        light_id,
        gl.GL_CONSTANT_ATTENUATION,
        0.5
    )

    gl.glLightf(
        light_id,
        gl.GL_LINEAR_ATTENUATION,
        0.08
    )


def setup_nightstand_light(lamp):
    if not lamp.is_on:
        gl.glDisable(
            gl.GL_LIGHT2
        )
        return

    gl.glEnable(
        gl.GL_LIGHT2
    )

    gl.glLightfv(
        gl.GL_LIGHT2,
        gl.GL_POSITION,
        [
            lamp.x,
            lamp.light_y,
            lamp.z,
            1.0
        ]
    )

    gl.glLightfv(
        gl.GL_LIGHT2,
        gl.GL_DIFFUSE,
        [
            1.0,
            0.70,
            0.30,
            1.0
        ]
    )

    gl.glLightfv(
        gl.GL_LIGHT2,
        gl.GL_SPECULAR,
        [
            1.0,
            0.70,
            0.30,
            1.0
        ]
    )

    gl.glLightf(
        gl.GL_LIGHT2,
        gl.GL_CONSTANT_ATTENUATION,
        0.8
    )

    gl.glLightf(
        gl.GL_LIGHT2,
        gl.GL_LINEAR_ATTENUATION,
        0.25
    )


def update_motion_lights(
    game,
    previous_x,
    previous_z,
    delta_time
):
    moved = (
        abs(
            game.player.x
            - previous_x
        ) > 0.0001
        or
        abs(
            game.player.z
            - previous_z
        ) > 0.0001
    )

    update_room_motion_timer(
        game.motion_timers,
        "room1",
        inside_room1(
            game.player.x,
            game.player.z
        ),
        moved,
        delta_time
    )

    update_room_motion_timer(
        game.motion_timers,
        "room2",
        inside_room2(
            game.player.x,
            game.player.z
        ),
        moved,
        delta_time
    )

    room1_light_on = (
        game.motion_timers["room1"]
        < MOTION_LIGHT_OFF_DELAY
    )

    room2_light_on = (
        game.motion_timers["room2"]
        < MOTION_LIGHT_OFF_DELAY
    )

    game.ceiling_lamp.is_on = room1_light_on
    game.nightstand_lamp.is_on = room1_light_on
    game.room2_lamp.is_on = room2_light_on


def update_room_motion_timer(
    timers,
    room_name,
    inside_room,
    moved,
    delta_time
):
    if inside_room and moved:
        timers[room_name] = 0.0
        return

    timers[room_name] = min(
        timers[room_name] + delta_time,
        MOTION_LIGHT_OFF_DELAY
    )


def draw_ui_text(
    text,
    x,
    y
):
    font = pygame.font.Font(
        None,
        28
    )

    surface = font.render(
        text,
        True,
        (
            255,
            255,
            255
        )
    )

    surface = pygame.transform.flip(
        surface,
        False,
        True
    )

    text_data = pygame.image.tostring(
        surface,
        "RGBA",
        True
    )

    width = surface.get_width()
    height = surface.get_height()

    gl.glMatrixMode(
        gl.GL_PROJECTION
    )

    gl.glPushMatrix()
    gl.glLoadIdentity()

    gl.glOrtho(
        0,
        WIDTH,
        0,
        HEIGHT,
        -1,
        1
    )

    gl.glMatrixMode(
        gl.GL_MODELVIEW
    )

    gl.glPushMatrix()
    gl.glLoadIdentity()

    gl.glDisable(
        gl.GL_DEPTH_TEST
    )

    gl.glDisable(
        gl.GL_LIGHTING
    )

    gl.glRasterPos2i(
        x,
        HEIGHT - y - height
    )

    gl.glDrawPixels(
        width,
        height,
        gl.GL_RGBA,
        gl.GL_UNSIGNED_BYTE,
        text_data
    )

    gl.glEnable(
        gl.GL_LIGHTING
    )

    gl.glEnable(
        gl.GL_DEPTH_TEST
    )

    gl.glPopMatrix()

    gl.glMatrixMode(
        gl.GL_PROJECTION
    )

    gl.glPopMatrix()

    gl.glMatrixMode(
        gl.GL_MODELVIEW
    )


def setup_opengl():
    gl.glEnable(
        gl.GL_DEPTH_TEST
    )

    gl.glEnable(
        gl.GL_COLOR_MATERIAL
    )

    gl.glColorMaterial(
        gl.GL_FRONT_AND_BACK,
        gl.GL_AMBIENT_AND_DIFFUSE
    )

    gl.glClearColor(
        0.45,
        0.65,
        0.90,
        1.0
    )

    gl.glMatrixMode(
        gl.GL_PROJECTION
    )

    gl.glLoadIdentity()

    glu.gluPerspective(
        75,
        WIDTH / HEIGHT,
        0.1,
        100.0
    )

    gl.glMatrixMode(
        gl.GL_MODELVIEW
    )

    gl.glEnable(
        gl.GL_LIGHTING
    )

    gl.glEnable(
        gl.GL_LIGHT0
    )

    gl.glLightfv(
        gl.GL_LIGHT0,
        gl.GL_AMBIENT,
        [
            0.18,
            0.18,
            0.18,
            1.0
        ]
    )

    gl.glLightfv(
        gl.GL_LIGHT0,
        gl.GL_DIFFUSE,
        [
            0.25,
            0.25,
            0.25,
            1.0
        ]
    )

    gl.glLightfv(
        gl.GL_LIGHT0,
        gl.GL_SPECULAR,
        [
            0.2,
            0.2,
            0.2,
            1.0
        ]
    )


def save_game(game):
    data = {
        "player": {
            "x": game.player.x,
            "y": game.player.y,
            "z": game.player.z,
            "yaw": game.player.yaw,
            "pitch": game.player.pitch
        },
        "exterior_door_open": (
            game.exterior_door.open
        ),
        "window_open": (
            game.window.open
        ),
        "lights_on": (
            game.ceiling_lamp.is_on
        )
    }

    temp_file = (
        SAVE_FILE
        + ".tmp"
    )

    try:
        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4
            )

            file.flush()

            os.fsync(
                file.fileno()
            )

        os.replace(
            temp_file,
            SAVE_FILE
        )

    except OSError:

        if os.path.exists(
            temp_file
        ):

            try:
                os.remove(
                    temp_file
                )

            except OSError:
                pass

        raise


def load_player_data(
    player,
    data
):
    player.x = data["x"]
    player.y = data["y"]
    player.z = data["z"]
    player.yaw = data["yaw"]
    player.pitch = data["pitch"]


def reset_invalid_player_position(
    player,
    game
):
    if object_collision_in_room1(
        player.x,
        player.z,
        game
    ):
        player.x = 0.0
        player.z = 0.0


def load_door_state(
    door,
    is_open
):
    door.open = is_open
    door.angle = (
        90.0
        if is_open
        else 0.0
    )

    door.target_angle = (
        door.angle
    )


def load_window_state(
    window,
    is_open
):
    window.open = is_open

    window.left_offset = (
        WINDOW_WIDTH / 2
        if is_open
        else 0.0
    )

    window.target_offset = (
        window.left_offset
    )


def load_light_state(
    game,
    lights_on
):
    game.ceiling_lamp.is_on = lights_on
    game.nightstand_lamp.is_on = lights_on
    game.room2_lamp.is_on = lights_on


def load_game(game):
    if not os.path.exists(
        SAVE_FILE
    ):
        return

    try:
        with open(
            SAVE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        load_player_data(
            game.player,
            data["player"]
        )

        reset_invalid_player_position(
            game.player,
            game
        )

        load_door_state(
            game.exterior_door,
            data.get(
                "exterior_door_open",
                False
            )
        )

        load_window_state(
            game.window,
            data.get(
                "window_open",
                False
            )
        )

        load_light_state(
            game,
            data.get(
                "lights_on",
                True
            )
        )

    except (
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError
    ):

        print(
            "Spielstand konnte nicht geladen werden."
        )


def show_message(message):
    pygame.display.set_caption(
        "Mein 3D-Spiel - "
        + message
    )


def get_day_status(
    sun_altitude
):
    if sun_altitude < -6.0:
        return "NACHT"

    if sun_altitude < 0.0:
        return "DÄMMERUNG"

    return "TAG"


class Game:

    def __init__(self):
        self.player = Player()

        self.exterior_door = ExteriorDoor()
        self.window = Window()

        self.bed = Bed()
        self.nightstand = Nightstand()
        self.table = Table()
        self.nightstand_lamp = NightstandLamp()

        self.chairs = [
            Chair(
                -1.55,
                -9.0,
                -90.0
            ),
            Chair(
                1.55,
                -9.0,
                90.0
            ),
            Chair(
                0.0,
                -10.60,
                180.0
            )
        ]

        room2_center_z = (
            ROOM2_MIN_Z
            + ROOM2_MAX_Z
        ) / 2

        self.ceiling_lamp = CeilingLamp(
            0.0,
            0.0
        )

        self.room2_lamp = CeilingLamp(
            0.0,
            room2_center_z
        )

        self.motion_timers = {
            "room1": MOTION_LIGHT_OFF_DELAY,
            "room2": MOTION_LIGHT_OFF_DELAY
        }

        self.autosave_timer = 0.0

        self.previous_x = self.player.x
        self.previous_z = self.player.z

    def initialize(self):
        pygame.init()

        pygame.display.set_mode(
            (
                WIDTH,
                HEIGHT
            ),
            pygame.DOUBLEBUF
            | pygame.OPENGL
        )

        pygame.display.set_caption(
            "Mein 3D-Spiel - Raum 1"
        )

        setup_opengl()

        pygame.mouse.set_visible(
            False
        )

        pygame.event.set_grab(
            True
        )

        load_game(
            self
        )

    def run(self):
        self.initialize()

        clock = pygame.time.Clock()
        running = True

        while running:
            delta_time = (
                clock.tick(60)
                / 1000.0
            )

            now = datetime.now()

            sky = get_sky_state(
                now
            )

            update_sky(
                sky
            )

            running = self.handle_events()

            self.update(
                delta_time
            )

            self.render(
                sky,
                now
            )

        pygame.quit()

    def handle_events(self):
        for event in pygame.event.get():

            if event.type == pygame.QUIT:

                save_game(
                    self
                )

                return False

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:

                    save_game(
                        self
                    )

                    return False

                if event.key == pygame.K_e:
                    self.handle_interaction()

        mouse_x, mouse_y = pygame.mouse.get_rel()

        self.player.mouse_look(
            mouse_x,
            mouse_y
        )

        return True

    def handle_interaction(self):
        interaction = self.get_interaction()

        if interaction is None:
            return

        action, target = interaction

        if action == "toggle_door":
            target.toggle()
            return

        if action == "toggle_window":
            target.toggle()
            return

        if action == "pickup":
            target.pick_up()

            show_message(
                target.name
                + " aufgenommen"
            )

            return

        if action == "place":

            target.put_down(
                self.player
            )

            show_message(
                target.name
                + " abgestellt"
            )

    def get_interaction(self):
        held_object = self.get_held_object()

        if held_object is not None:
            return (
                "place",
                held_object
            )

        if inside_room1(
            self.player.x,
            self.player.z
        ):

            if self.nightstand_lamp.is_near(
                self.player
            ):
                return (
                    "pickup",
                    self.nightstand_lamp
                )

        if can_interact_with_exterior_door(
            self.player
        ):
            return (
                "toggle_door",
                self.exterior_door
            )

        if can_interact_with_window(
            self.player,
            self.window
        ):
            return (
                "toggle_window",
                self.window
            )

        if inside_room2(
            self.player.x,
            self.player.z
        ):

            if self.table.is_near(
                self.player
            ):
                return (
                    "pickup",
                    self.table
                )

            for chair in self.chairs:

                if chair.is_near(
                    self.player
                ):
                    return (
                        "pickup",
                        chair
                    )

        if inside_room1(
            self.player.x,
            self.player.z
        ):

            if self.bed.is_near(
                self.player
            ):
                return (
                    "pickup",
                    self.bed
                )

            if self.nightstand.is_near(
                self.player
            ):
                return (
                    "pickup",
                    self.nightstand
                )

        return None

    def get_held_object(self):
        for obj in self.carryable_objects():

            if obj.held:
                return obj

        return None

    def carryable_objects(self):
        return [
            self.bed,
            self.nightstand,
            self.table,
            *self.chairs,
            self.nightstand_lamp
        ]

    def update(self, delta_time):
        keys = pygame.key.get_pressed()

        self.player.move(
            keys,
            delta_time,
            self
        )

        self.update_held_objects()

        update_motion_lights(
            self,
            self.previous_x,
            self.previous_z,
            delta_time
        )

        self.previous_x = (
            self.player.x
        )

        self.previous_z = (
            self.player.z
        )

        self.exterior_door.update(
            delta_time
        )

        self.window.update(
            delta_time
        )

        self.update_autosave(
            delta_time
        )

        self.update_window_title()

    def update_held_objects(self):
        for obj in self.carryable_objects():
            obj.update_held_position(
                self.player
            )

    def update_autosave(
        self,
        delta_time
    ):
        self.autosave_timer += (
            delta_time
        )

        if (
            self.autosave_timer
            >= AUTOSAVE_INTERVAL
        ):

            save_game(
                self
            )

            self.autosave_timer = 0.0

    def update_window_title(self):
        room = get_current_room(
            self.player
        )

        interaction = self.get_interaction()

        title = (
            "Mein 3D-Spiel - "
            + room
        )

        if interaction is not None:

            action, target = interaction

            title += (
                " - "
                + self.interaction_text(
                    action,
                    target
                )
            )

        pygame.display.set_caption(
            title
        )

    def interaction_text(
        self,
        action,
        target
    ):
        if action == "place":

            return (
                "E - "
                + target.name
                + " abstellen"
            )

        if action == "pickup":

            return (
                "E - "
                + target.name
                + " aufnehmen"
            )

        if action == "toggle_door":

            state = (
                "schließen"
                if target.is_open()
                else "öffnen"
            )

            return (
                "E - Außentür "
                + state
            )

        if action == "toggle_window":

            state = (
                "schließen"
                if target.open
                else "öffnen"
            )

            return (
                "E - Fenster "
                + state
            )

        return ""

    def render(
        self,
        sky,
        now
    ):
        gl.glClear(
            gl.GL_COLOR_BUFFER_BIT
            | gl.GL_DEPTH_BUFFER_BIT
        )

        gl.glLoadIdentity()

        self.player.apply_camera()

        update_sun_light(
            sky
        )

        update_moon_light(
            sky
        )

        setup_ceiling_light(
            self.ceiling_lamp,
            gl.GL_LIGHT1
        )

        setup_ceiling_light(
            self.room2_lamp,
            gl.GL_LIGHT3
        )

        setup_nightstand_light(
            self.nightstand_lamp
        )

        self.draw_scene(
            sky
        )

        self.draw_ui(
            sky,
            now
        )

        pygame.display.flip()

    def draw_scene(
        self,
        sky
    ):
        draw_sun(
            sky
        )

        draw_moon(
            sky
        )

        draw_world()

        for street_lamp in STREET_LAMPS:

            street_lamp.draw(
                sky["is_night"]
            )

        room2_center_z = (
            ROOM2_MIN_Z
            + ROOM2_MAX_Z
        ) / 2

        draw_room_floor(
            0.0
        )

        draw_room_ceiling(
            0.0
        )

        draw_room1_walls()

        draw_room_floor(
            room2_center_z
        )

        draw_room_ceiling(
            room2_center_z
        )

        draw_room2_walls()

        draw_exterior_door(
            self.exterior_door
        )

        draw_window(
            self.window
        )

        draw_bed(
            self.bed
        )

        draw_nightstand(
            self.nightstand
        )

        draw_table(
            self.table
        )

        for chair in self.chairs:

            draw_chair(
                chair
            )

        draw_nightstand_lamp(
            self.nightstand_lamp
        )

        draw_ceiling_lamp(
            self.ceiling_lamp
        )

        draw_ceiling_lamp(
            self.room2_lamp
        )

    def draw_ui(
        self,
        sky,
        now
    ):
        time_text = now.strftime(
            "%d.%m.%Y  %H:%M:%S"
        )

        status_text = get_day_status(
            sky["sun_altitude"]
        )

        phase_text = moon_phase_name(
            sky["moon_phase"]
        )

        draw_ui_text(
            time_text,
            25,
            25
        )

        draw_ui_text(
            status_text,
            25,
            60
        )

        draw_ui_text(
            "Mond: " + phase_text,
            25,
            95
        )


if __name__ == "__main__":
    Game().run()