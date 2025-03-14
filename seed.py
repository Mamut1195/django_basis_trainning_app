from daily_trainning_app.models import Classification, Exercise, User, UserExerciseRM, WorkoutData
import os
import django
import random
from datetime import datetime, timedelta

# 📌 Configurar Django
# Asegúrate de que sea el nombre correcto del proyecto
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "basis_trainning_app.settings")
django.setup()


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
            ("Sentadilla",
             "https://youtube.com/sentadilla",
             "Ejercicio fundamental para piernas.")],
        "Chest": [
            ("Press de Banca",
             "https://youtube.com/pressbanca",
             "Ejercicio principal para pectorales.")],
        "Back - Lats": [
            ("Dominadas",
             "https://youtube.com/dominadas",
             "Ejercicio de espalda con peso corporal.")]}

    for category_name, exercises in exercises_by_category.items():
        classification = Classification.objects.filter(
            nombre=category_name).first()
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

    users_data = [
        ("Juan Pérez", "juan@example.com", "2024-01-10"),
        ("Ana López", "ana@example.com", "2024-02-05"),
        ("Carlos Ramírez", "carlos@example.com", "2023-12-20"),
    ]

    for nombre, email, fecha_inicio in users_data:
        User.objects.create(
            nombre=nombre,
            email=email,
            fecha_inicio=fecha_inicio)
        print(f"✅ Usuario creado: {nombre} - {email}")

    print("🎉 ¡Usuarios generados exitosamente!")


def seed_user_exercise_rm():
    UserExerciseRM.objects.all().delete()
    print("🗑️ Se eliminaron todos los registros de 1RM.")

    users = User.objects.all()
    exercises = Exercise.objects.all()

    if not users.exists() or not exercises.exists():
        print("⚠️ No hay usuarios o ejercicios creados. Ejecuta `seed_users()` y `seed_exercises()` primero.")
        return

    for user in users:
        for exercise in random.sample(
            list(exercises),
            k=min(
                3,
                len(exercises))):  # Asigna hasta 3 ejercicios por usuario
            peso_maximo_rm = random.randint(80, 200)  # Peso aleatorio en kg
            fecha_registro = datetime.now() - timedelta(days=random.randint(1, 365))

            UserExerciseRM.objects.create(
                user=user,
                exercise=exercise,
                peso_maximo_rm=peso_maximo_rm,
                fecha_registro=fecha_registro
            )

            print(
                f"✅ 1RM creado: {user.nombre} - {exercise.nombre}: {peso_maximo_rm} kg")

    print("🎉 ¡Registros de 1RM generados exitosamente!")


def seed_workout_data():
    WorkoutData.objects.all().delete()
    print("🗑️ Se eliminaron todos los datos de entrenamientos.")

    users = User.objects.all()
    exercises = Exercise.objects.all()

    if not users.exists() or not exercises.exists():
        print("⚠️ No hay usuarios o ejercicios creados. Ejecuta `seed_users()` y `seed_exercises()` primero.")
        return

    for _ in range(20):  # Generar 20 entrenamientos
        user = random.choice(users)
        exercise = random.choice(exercises)
        rm_entry = UserExerciseRM.objects.filter(
            user=user, exercise=exercise).first()

        if not rm_entry:
            continue  # Si no hay RM registrado, pasar al siguiente

        fecha = datetime.now() - timedelta(days=random.randint(1, 30))
        sets = random.randint(3, 5)
        reps = random.randint(8, 12)
        peso = random.randint(int(rm_entry.peso_maximo_rm * 0.6),
                              int(rm_entry.peso_maximo_rm * 0.9))

        # 📌 Crear el objeto `WorkoutData` sin calcular manualmente los valores
        workout = WorkoutData(
            user=user,
            exercise=exercise,
            fecha=fecha,
            sets=sets,
            reps=reps,
            peso=peso
        )

        # 📌 Llamar al método `clean()` del modelo para calcular los valores automáticamente
        workout.clean()
        workout.save()

        print(
            f"✅ Workout creado: {user.nombre} - {exercise.nombre} en {fecha.date()}")

    print("🎉 ¡Workouts generados exitosamente!")


# 📌 Ejecutar las funciones en orden correcto
seed_classifications()
seed_exercises()
seed_users()
seed_user_exercise_rm()
seed_workout_data()
