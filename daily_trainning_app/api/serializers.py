from rest_framework import serializers
from daily_trainning_app.models import Classification, Exercise, User, UserExerciseRM, WorkoutData

# 📌 1️⃣ Serializer para Clasificación


class ClassificationSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(max_length=255)

    class Meta:
        model = Classification
        fields = ["id", "nombre"]  # No exponemos datos innecesarios

    def validate_nombre(self, value):
        """ Normaliza y valida el nombre """
        return value.strip().title()


# 📌 2️⃣ Serializer para Ejercicios
class ExerciseSerializer(serializers.ModelSerializer):
    classification = ClassificationSerializer(
        read_only=True)  # Datos completos de clasificación
    classification_id = serializers.PrimaryKeyRelatedField(
        queryset=Classification.objects.all(),
        source="classification",
        write_only=True)  # Permitir asignar clasificación por ID

    class Meta:
        model = Exercise
        fields = [
            "id",
            "nombre",
            "video",
            "descripcion",
            "classification",
            "classification_id"]

    def validate_nombre(self, value):
        """ Normaliza y valida el nombre """
        return value.strip().title()


# 📌 3️⃣ Serializer para Usuarios (Sin Exponer Datos Sensibles)
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # ⚠️ No exponemos contraseñas ni datos innecesarios
        fields = ["id", "nombre", "email", "fecha_inicio"]

    def validate_email(self, value):
        """ Validar que el email tenga un formato correcto """
        if "@" not in value:
            raise serializers.ValidationError("Debe ser un email válido.")
        return value.lower().strip()


# 📌 4️⃣ Serializer para UserExerciseRM (Registros de 1RM por Usuario y Ejercicio)
class UserExerciseRMSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # Solo lectura del usuario
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True
    )  # Permitir enviar solo el ID

    exercise = ExerciseSerializer(read_only=True)  # Solo lectura del ejercicio
    exercise_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercise.objects.all(), source="exercise", write_only=True
    )  # Permitir enviar solo el ID

    class Meta:
        model = UserExerciseRM
        fields = [
            "id",
            "user",
            "user_id",
            "exercise",
            "exercise_id",
            "peso_maximo_rm",
            "fecha_registro"]

    def validate_peso_maximo_rm(self, value):
        """ Asegurar que el peso máximo registrado sea un número válido """
        if value <= 0:
            raise serializers.ValidationError("El 1RM debe ser mayor a 0.")
        return value


# 📌 5️⃣ Serializer para WorkoutData (Datos de Entrenamientos con Cálculos Automáticos)
class WorkoutDataSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True)

    exercise = ExerciseSerializer(read_only=True)
    exercise_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercise.objects.all(), source="exercise", write_only=True)

    intensidad_relativa = serializers.FloatField(
        read_only=True)  # Calculado automáticamente
    carga = serializers.FloatField(read_only=True)  # Calculado automáticamente
    volumen_relativo = serializers.FloatField(
        read_only=True)  # Calculado automáticamente
    rpe_objetivo = serializers.FloatField(
        read_only=True)  # Calculado automáticamente
    rm_sesion = serializers.FloatField(
        read_only=True)  # Calculado automáticamente

    class Meta:
        model = WorkoutData
        fields = [
            "id",
            "user",
            "user_id",
            "exercise",
            "exercise_id",
            "fecha",
            "sets",
            "reps",
            "peso",
            "carga",
            "intensidad_relativa",
            "volumen_relativo",
            "rpe_objetivo",
            "rm_sesion"]

    def validate_peso(self, value):
        """ Asegurar que el peso utilizado sea mayor a 0 """
        if value < 0:
            raise serializers.ValidationError("El peso no puede ser negativo.")
        return value

    def create(self, validated_data):
        """ Crear y calcular automáticamente los valores de entrenamiento """
        instance = WorkoutData(**validated_data)
        # Calcular automáticamente carga, volumen, intensidad, etc.
        instance.clean()
        instance.save()
        return instance
