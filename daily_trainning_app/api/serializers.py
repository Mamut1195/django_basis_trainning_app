from rest_framework import serializers
from .models import Classification, Exercise, User, WorkoutData


class ClassificationSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(max_length=255)

    class Meta:
        model = Classification
        fields = ['id', 'nombre']  # Evita usar '__all__'

    def validate_nombre(self, value):
        """ Normaliza y valida el nombre """
        return value.strip().title()


class ExerciseSerializer(serializers.ModelSerializer):
    # Muestra detalles completos de clasificación
    classification = ClassificationSerializer(read_only=True)
    classification_id = serializers.PrimaryKeyRelatedField(
        queryset=Classification.objects.all(),
        source='classification',
        write_only=True)  # Permite enviar solo el ID en POST

    class Meta:
        model = Exercise
        fields = [
            'id',
            'nombre',
            'video',
            'descripcion',
            'classification',
            'classification_id']

    def validate_nombre(self, value):
        return value.strip().title()


class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()

    class Meta:
        model = User
        fields = ['id', 'nombre', 'email', 'fecha_inicio']

    def validate_nombre(self, value):
        return value.strip().title()

    def validate_email(self, value):
        """ Verifica que el email no esté en uso """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email ya está registrado.")
        return value


class WorkoutDataSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # Datos completos del usuario
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )  # Permite enviar solo el ID

    exercise = ExerciseSerializer(read_only=True)
    exercise_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercise.objects.all(), source='exercise', write_only=True
    )

    class Meta:
        model = WorkoutData
        fields = [
            'id', 'user', 'user_id', 'exercise', 'exercise_id',
            'fecha', 'sets', 'reps', 'total_reps', 'carga',
            'intensidad_relativa', 'volumen_relativo', 'rpe_objetivo'
        ]

    def validate_sets(self, value):
        """ Validar que los sets sean un número positivo """
        if value < 0:
            raise serializers.ValidationError(
                "Los sets deben ser un número positivo.")
        return value

    def validate_reps(self, value):
        """ Validar que las reps sean un número positivo """
        if value < 0:
            raise serializers.ValidationError(
                "Las repeticiones deben ser un número positivo.")
        return value

    def validate(self, data):
        """ Calcula automáticamente `total_reps` basado en sets y reps """
        sets = data.get('sets', 0)
        reps = data.get('reps', 0)
        data['total_reps'] = sets * reps
        return data
