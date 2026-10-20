"""Retired destructive seed source, retained for reference only."""

# Reject both execution and import before Django can open any database.
raise RuntimeError(
    "Legacy seed retired: destructive helpers are disabled. "
    "Use manage.py seed_demo only against an isolated local demonstration database."
)

import os
import django
import random
from datetime import datetime, timedelta

from django.forms import ValidationError

# ✅ CONFIGURA DJANGO ANTES DE IMPORTAR MODELOS
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "basis_trainning_app.settings")
django.setup()

# ✅ AHORA IMPORTA LOS MODELOS
from daily_trainning_app.models import Classification, Exercise, User, UserExerciseRM, WorkoutData

def normalize_text(text):
    return text.strip().title()


def seed_classifications():
    Classification.objects.all().delete()
    print("🗑️ Se eliminaron todas las clasificaciones existentes.")

    classifications = [
        "Quads", "Hamstrings", "Glutes", "Calves",
        "Chest", "Back - Lats", "Back - Traps",
        "Shoulders", "Biceps", "Triceps", "Forearms",
        "Abs", "Lower Back"
    ]

    for name in classifications:
        Classification.objects.create(nombre=name)
        print(f"✅ Creada: {name}")

    print("🎉 ¡Clasificaciones generadas exitosamente!")


def seed_exercises():
    Exercise.objects.all().delete()
    print("🗑️ Se eliminaron todos los ejercicios existentes.")

    exercises_by_category = {
        "Quads": [
            ("Sentadilla", "https://youtube.com/sentadilla", "Ejercicio fundamental para piernas.")
        ],
        "Chest": [
            ("Press de Banca", "https://youtube.com/pressbanca", "Ejercicio principal para pectorales.")
        ],
        "Back - Lats": [
            ("Dominadas", "https://youtube.com/dominadas", "Ejercicio de espalda con peso corporal.")
        ]
    }

    for category_name, exercises in exercises_by_category.items():
        classification = Classification.objects.filter(nombre=category_name).first()
        if classification:
            for nombre, video, descripcion in exercises:
                Exercise.objects.create(
                    nombre=nombre,
                    video=video,
                    descripcion=descripcion,
                    classification=classification
                )
                print(f"✅ Creado: {nombre} en {category_name}")
        else:
            print(f"⚠️ No se encontró la clasificación: {category_name}")

    print("🎉 ¡Ejercicios generados exitosamente!")


def seed_users():
    User.objects.all().delete()
    print("🗑️ Se eliminaron todos los usuarios existentes.")

    def format_objetivos(*objetivos):
        return "\n".join(objetivos)

    users_data = [
        ("Juan Pérez", "juan@example.com", "2024-01-10", "Entrenador", "Ecuador", "Quito", "Fuerza", 28, 78.5,
         format_objetivos("Aumentar masa muscular", "Mejorar técnica en sentadilla", "Reducir grasa corporal"),
         "Me gusta entrenar 5 días a la semana."),

        ("Ana López", "ana@example.com", "2024-02-05", "Atleta", "Ecuador", "Guayaquil", "Hipertrofia", 24, 60.2,
         format_objetivos("Tonificar piernas", "Aumentar fuerza en tren superior", "Mejorar movilidad"),
         "Prefiero rutinas con poco descanso."),

        ("Carlos Ramírez", "carlos@example.com", "2023-12-20", "Coach", "Colombia", "Medellín", "Crossfit", 35, 85.3,
         format_objetivos("Aumentar capacidad aeróbica", "Mejorar técnica de levantamiento olímpico", "Reducir tiempo en WODs"),
         "Practico crossfit desde 2020."),

        ("Luisa Gómez", "luisa@example.com", "2023-11-15", "Nutricionista", "Perú", "Lima", "Salud general", 31, 55.0,
         format_objetivos("Mantenerme activa", "Evitar lesiones", "Mejorar postura"),
         "Trabajo en el sector salud."),

        ("Miguel Torres", "miguel@example.com", "2024-03-01", "Fisioterapeuta", "Chile", "Santiago", "Recuperación", 40, 90.0,
         format_objetivos("Recuperarme de lesión", "Fortalecer rodilla", "Mejorar rango articular"),
         "Tuve una lesión en la pierna."),

        ("Elena Ríos", "elena@example.com", "2024-01-25", "Estudiante", "Argentina", "Buenos Aires", "Fuerza", 22, 58.4,
         format_objetivos("Ganar fuerza", "Aprender técnica de peso muerto", "Desarrollar glúteos"),
         "Estoy empezando con la fuerza."),

        ("Pedro Vega", "pedro@example.com", "2024-02-10", "Ingeniero", "México", "CDMX", "Hipertrofia", 30, 82.1,
         format_objetivos("Ganar volumen", "Mantener bajo porcentaje de grasa", "Mejorar rendimiento general"),
         "Entreno por las noches."),

        ("Sofía Herrera", "sofia@example.com", "2024-03-15", "Arquitecta", "España", "Madrid", "Definición", 27, 62.0,
         format_objetivos("Reducir grasa corporal", "Aumentar tono muscular", "Seguir un plan consistente"),
         "Uso app de seguimiento."),

        ("Daniel Morales", "daniel@example.com", "2024-01-30", "Estudiante", "Ecuador", "Cuenca", "Fuerza", 20, 73.5,
         format_objetivos("Ganar fuerza y potencia", "Participar en competencia estudiantil", "Aumentar masa magra"),
         "Entreno en casa."),

        ("Camila Bustos", "camila@example.com", "2024-04-05", "Profesora", "Uruguay", "Montevideo", "Resistencia", 33, 64.8,
         format_objetivos("Mejorar condición física", "Correr 5K en menos de 30 minutos", "Evitar fatiga diaria"),
         "Me gusta entrenar en grupo."),

        ("Felipe Acosta", "felipe@example.com", "2023-12-01", "Chef", "Paraguay", "Asunción", "Cardio", 29, 70.0,
         format_objetivos("Perder peso", "Bajar de 85kg a 75kg", "Aumentar energía diaria"),
         "Entreno 4 veces a la semana."),

        ("Mariana Silva", "mariana@example.com", "2024-02-22", "Diseñadora", "Brasil", "São Paulo", "Tonificación", 26, 61.2,
         format_objetivos("Definir músculos", "Reducir cintura", "Mejorar postura"),
         "Sigo una dieta personalizada."),

        ("Hugo Martínez", "hugo@example.com", "2024-03-10", "Abogado", "Bolivia", "La Paz", "Powerlifting", 38, 95.0,
         format_objetivos("Mejorar 1RM", "Preparar para torneo local", "Optimizar descanso"),
         "Compito en amateur."),

        ("Andrea Reyes", "andrea@example.com", "2024-01-18", "Contadora", "Panamá", "Panamá", "Fitness general", 32, 59.9,
         format_objetivos("Mantenerme saludable", "Evitar sedentarismo", "Establecer rutina constante"),
         "Prefiero entrenamientos funcionales."),

        ("Esteban Soto", "esteban@example.com", "2024-03-28", "Entrenador", "Ecuador", "Loja", "Fuerza e hipertrofia", 36, 88.6,
         format_objetivos("Programar rutinas personalizadas", "Mantener volumen en offseason", "Progresar en sentadilla frontal"),
         "Trabajo con atletas.")
    ]

    for data in users_data:
        user = User(
            nombre=data[0],
            email=data[1],
            fecha_inicio=data[2],
            titulo=data[3],
            pais=data[4],
            ciudad=data[5],
            especialidad=data[6],
            edad=data[7],
            peso=data[8],
            objetivos=data[9],
            descripcion=data[10],
        )
        try:
            user.clean()
            user.save()
            print(f"✅ Usuario creado: {user.nombre}")
        except ValidationError as e:
            print(f"❌ Error creando usuario {user.nombre}: {e}")

    print("🎉 ¡15 Usuarios generados exitosamente con objetivos múltiples!")

    User.objects.all().delete()
    print("🗑️ Se eliminaron todos los usuarios existentes.")

    users_data = [
        ("Juan Pérez", "juan@example.com", "2024-01-10", "Entrenador", "Ecuador", "Quito", "Fuerza", 28, 78.5, "Aumentar masa muscular", "Me gusta entrenar 5 días a la semana."),
        ("Ana López", "ana@example.com", "2024-02-05", "Atleta", "Ecuador", "Guayaquil", "Hipertrofia", 24, 60.2, "Tonificar el cuerpo", "Prefiero rutinas con poco descanso."),
        ("Carlos Ramírez", "carlos@example.com", "2023-12-20", "Coach", "Colombia", "Medellín", "Crossfit", 35, 85.3, "Mejorar resistencia", "Practico crossfit desde 2020."),
        ("Luisa Gómez", "luisa@example.com", "2023-11-15", "Nutricionista", "Perú", "Lima", "Salud general", 31, 55.0, "Mantenerme activa", "Trabajo en el sector salud."),
        ("Miguel Torres", "miguel@example.com", "2024-03-01", "Fisioterapeuta", "Chile", "Santiago", "Recuperación", 40, 90.0, "Recuperarme de lesión", "Tuve una lesión en la pierna."),
        ("Elena Ríos", "elena@example.com", "2024-01-25", "Estudiante", "Argentina", "Buenos Aires", "Fuerza", 22, 58.4, "Ganar fuerza", "Estoy empezando con la fuerza."),
        ("Pedro Vega", "pedro@example.com", "2024-02-10", "Ingeniero", "México", "CDMX", "Hipertrofia", 30, 82.1, "Ganar volumen", "Entreno por las noches."),
        ("Sofía Herrera", "sofia@example.com", "2024-03-15", "Arquitecta", "España", "Madrid", "Definición", 27, 62.0, "Reducir grasa corporal", "Uso app de seguimiento."),
        ("Daniel Morales", "daniel@example.com", "2024-01-30", "Estudiante", "Ecuador", "Cuenca", "Fuerza", 20, 73.5, "Ganar fuerza y potencia", "Entreno en casa."),
        ("Camila Bustos", "camila@example.com", "2024-04-05", "Profesora", "Uruguay", "Montevideo", "Resistencia", 33, 64.8, "Mejorar condición física", "Me gusta entrenar en grupo."),
        ("Felipe Acosta", "felipe@example.com", "2023-12-01", "Chef", "Paraguay", "Asunción", "Cardio", 29, 70.0, "Perder peso", "Entreno 4 veces a la semana."),
        ("Mariana Silva", "mariana@example.com", "2024-02-22", "Diseñadora", "Brasil", "São Paulo", "Tonificación", 26, 61.2, "Definir músculos", "Sigo una dieta personalizada."),
        ("Hugo Martínez", "hugo@example.com", "2024-03-10", "Abogado", "Bolivia", "La Paz", "Powerlifting", 38, 95.0, "Mejorar 1RM", "Compito en amateur."),
        ("Andrea Reyes", "andrea@example.com", "2024-01-18", "Contadora", "Panamá", "Panamá", "Fitness general", 32, 59.9, "Mantenerme saludable", "Prefiero entrenamientos funcionales."),
        ("Esteban Soto", "esteban@example.com", "2024-03-28", "Entrenador", "Ecuador", "Loja", "Fuerza e hipertrofia", 36, 88.6, "Programar rutinas personalizadas", "Trabajo con atletas.")
    ]

    for data in users_data:
        user = User(
            nombre=data[0],
            email=data[1],
            fecha_inicio=data[2],
            titulo=data[3],
            pais=data[4],
            ciudad=data[5],
            especialidad=data[6],
            edad=data[7],
            peso=data[8],
            objetivos=data[9],
            descripcion=data[10],
        )
        try:
            user.clean()
            user.save()
            print(f"✅ Usuario creado: {user.nombre}")
        except ValidationError as e:
            print(f"❌ Error creando usuario {user.nombre}: {e}")

    print("🎉 ¡15 Usuarios generados exitosamente!")


def seed_user_exercise_rm():
    UserExerciseRM.objects.all().delete()
    print("🗑️ Se eliminaron todos los registros de 1RM.")

    users = User.objects.all()
    exercises = Exercise.objects.all()

    if not users.exists() or not exercises.exists():
        print("⚠️ No hay usuarios o ejercicios creados.")
        return

    for user in users:
        for exercise in random.sample(list(exercises), k=min(2, len(exercises))):
            peso_maximo_rm = random.randint(70, 160)
            fecha_registro = datetime.now() - timedelta(days=random.randint(1, 180))

            UserExerciseRM.objects.create(
                user=user,
                exercise=exercise,
                peso_maximo_rm=peso_maximo_rm,
                fecha_registro=fecha_registro
            )
            print(f"✅ 1RM creado: {user.nombre} - {exercise.nombre} - {peso_maximo_rm}kg")

    print("🎉 ¡1RM generados exitosamente!")


def seed_workout_data():
    WorkoutData.objects.all().delete()
    print("🗑️ Se eliminaron todos los datos de entrenamientos.")

    users = User.objects.all()
    exercises = Exercise.objects.all()

    if not users.exists() or not exercises.exists():
        print("⚠️ No hay usuarios o ejercicios creados.")
        return

    for _ in range(25):
        user = random.choice(users)
        exercise = random.choice(exercises)
        rm_entry = UserExerciseRM.objects.filter(user=user, exercise=exercise).first()
        if not rm_entry:
            continue

        fecha = datetime.now() - timedelta(days=random.randint(1, 30))
        sets = random.randint(3, 5)
        reps = random.randint(8, 12)
        peso = random.randint(int(rm_entry.peso_maximo_rm * 0.6), int(rm_entry.peso_maximo_rm * 0.9))

        workout = WorkoutData(
            user=user,
            exercise=exercise,
            fecha=fecha,
            sets=sets,
            reps=reps,
            peso=peso
        )
        workout.clean()
        workout.save()
        print(f"✅ Workout: {user.nombre} - {exercise.nombre} - {fecha.date()}")

    print("🎉 ¡Workouts generados exitosamente!")


# 📌 Ejecutar las funciones en orden
def run_all_seeds():
    raise RuntimeError("El reinicio destructivo está deshabilitado. Usa manage.py seed_demo en una base local independiente.")
    seed_classifications()
    seed_exercises()
    seed_users()
    seed_user_exercise_rm()
    seed_workout_data()

# Si se ejecuta este archivo directamente:
if __name__ == "__main__":
    run_all_seeds()
