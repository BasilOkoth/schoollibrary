from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import schema_context

from tenants.models import School
from digitallibrary.models import Class, Subject


CBC_CLASS_DEFINITIONS = {
    "Grade 1": {
        "level": "PRIMARY",
        "curriculum": "CBC",
        "sort_order": 1,
        "requires_pathway": False,
        "is_legacy": False,
    },
    "Grade 2": {
        "level": "PRIMARY",
        "curriculum": "CBC",
        "sort_order": 2,
        "requires_pathway": False,
        "is_legacy": False,
    },
    "Grade 3": {
        "level": "PRIMARY",
        "curriculum": "CBC",
        "sort_order": 3,
        "requires_pathway": False,
        "is_legacy": False,
    },
    "Grade 4": {
        "level": "PRIMARY",
        "curriculum": "CBC",
        "sort_order": 4,
        "requires_pathway": False,
        "is_legacy": False,
    },
    "Grade 5": {
        "level": "PRIMARY",
        "curriculum": "CBC",
        "sort_order": 5,
        "requires_pathway": False,
        "is_legacy": False,
    },
    "Grade 6": {
        "level": "PRIMARY",
        "curriculum": "CBC",
        "sort_order": 6,
        "requires_pathway": False,
        "is_legacy": False,
    },
    "Grade 7": {
        "level": "JUNIOR",
        "curriculum": "CBC",
        "sort_order": 7,
        "requires_pathway": False,
        "is_legacy": False,
    },
    "Grade 8": {
        "level": "JUNIOR",
        "curriculum": "CBC",
        "sort_order": 8,
        "requires_pathway": False,
        "is_legacy": False,
    },
    "Grade 9": {
        "level": "JUNIOR",
        "curriculum": "CBC",
        "sort_order": 9,
        "requires_pathway": False,
        "is_legacy": False,
    },
}


LOWER_PRIMARY_LEARNING_AREAS = [
    {
        "name": "English Language Activities",
        "code": "CBC_LP_ENG",
        "result_code": 101,
        "order": 101,
    },
    {
        "name": "Kiswahili Language Activities",
        "code": "CBC_LP_KIS",
        "result_code": 102,
        "order": 102,
    },
    {
        "name": "Mathematical Activities",
        "code": "CBC_LP_MATH",
        "result_code": 103,
        "order": 103,
    },
    {
        "name": "Environmental Activities",
        "code": "CBC_LP_ENV",
        "result_code": 104,
        "order": 104,
    },
    {
        "name": "Creative Activities",
        "code": "CBC_LP_CREAT",
        "result_code": 105,
        "order": 105,
    },
    {
        "name": "Religious Education Activities",
        "code": "CBC_LP_RE",
        "result_code": 106,
        "order": 106,
    },
    {
        "name": "Movement Activities",
        "code": "CBC_LP_MOVE",
        "result_code": 107,
        "order": 107,
    },
]


UPPER_PRIMARY_LEARNING_AREAS = [
    {
        "name": "English",
        "code": "CBC_ENG",
        "result_code": 201,
        "order": 201,
    },
    {
        "name": "Kiswahili",
        "code": "CBC_KIS",
        "result_code": 202,
        "order": 202,
    },
    {
        "name": "Mathematics",
        "code": "CBC_MATH",
        "result_code": 203,
        "order": 203,
    },
    {
        "name": "Science and Technology",
        "code": "CBC_SCI_TECH",
        "result_code": 204,
        "order": 204,
    },
    {
        "name": "Agriculture and Nutrition",
        "code": "CBC_AGR_NUT",
        "result_code": 205,
        "order": 205,
    },
    {
        "name": "Social Studies",
        "code": "CBC_SOC_ST",
        "result_code": 206,
        "order": 206,
    },
    {
        "name": "Religious Education",
        "code": "CBC_RE",
        "result_code": 207,
        "order": 207,
    },
    {
        "name": "Creative Arts",
        "code": "CBC_CRE_ARTS",
        "result_code": 208,
        "order": 208,
    },
    {
        "name": "Physical and Health Education",
        "code": "CBC_PHE",
        "result_code": 209,
        "order": 209,
    },
]


JUNIOR_SCHOOL_LEARNING_AREAS = [
    {
        "name": "English",
        "code": "CBC_ENG",
        "result_code": 201,
        "order": 201,
    },
    {
        "name": "Kiswahili",
        "code": "CBC_KIS",
        "result_code": 202,
        "order": 202,
    },
    {
        "name": "Mathematics",
        "code": "CBC_MATH",
        "result_code": 203,
        "order": 203,
    },
    {
        "name": "Integrated Science",
        "code": "CBC_INT_SCI",
        "result_code": 301,
        "order": 301,
    },
    {
        "name": "Health Education",
        "code": "CBC_HEALTH",
        "result_code": 302,
        "order": 302,
    },
    {
        "name": "Pre-Technical Studies",
        "code": "CBC_PRE_TECH",
        "result_code": 303,
        "order": 303,
    },
    {
        "name": "Social Studies",
        "code": "CBC_SOC_ST",
        "result_code": 206,
        "order": 206,
    },
    {
        "name": "Religious Education",
        "code": "CBC_RE",
        "result_code": 207,
        "order": 207,
    },
    {
        "name": "Business Studies",
        "code": "CBC_BUS",
        "result_code": 304,
        "order": 304,
    },
    {
        "name": "Agriculture and Nutrition",
        "code": "CBC_AGR_NUT",
        "result_code": 205,
        "order": 205,
    },
    {
        "name": "Life Skills Education",
        "code": "CBC_LIFE",
        "result_code": 305,
        "order": 305,
    },
    {
        "name": "Sports and Physical Education",
        "code": "CBC_SPE",
        "result_code": 306,
        "order": 306,
    },
    {
        "name": "Creative Arts",
        "code": "CBC_CRE_ARTS",
        "result_code": 208,
        "order": 208,
    },
]


CLASS_LEARNING_AREA_MAP = {
    "Grade 1": LOWER_PRIMARY_LEARNING_AREAS,
    "Grade 2": LOWER_PRIMARY_LEARNING_AREAS,
    "Grade 3": LOWER_PRIMARY_LEARNING_AREAS,
    "Grade 4": UPPER_PRIMARY_LEARNING_AREAS,
    "Grade 5": UPPER_PRIMARY_LEARNING_AREAS,
    "Grade 6": UPPER_PRIMARY_LEARNING_AREAS,
    "Grade 7": JUNIOR_SCHOOL_LEARNING_AREAS,
    "Grade 8": JUNIOR_SCHOOL_LEARNING_AREAS,
    "Grade 9": JUNIOR_SCHOOL_LEARNING_AREAS,
}


class Command(BaseCommand):
    help = (
        "Seed CBC learning areas as Subject records and assign them to "
        "Grade 1 to Grade 9 through Subject.applicable_classes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema to seed, for example demo or ngegemixed.",
        )

        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Seed CBC learning areas for all tenant schools.",
        )

        parser.add_argument(
            "--create-missing-classes",
            action="store_true",
            help="Create Grade 1 to Grade 9 if they do not already exist.",
        )

        parser.add_argument(
            "--fix-class-metadata",
            action="store_true",
            help="Update Grade 1 to Grade 9 level, curriculum, sort_order and pathway settings.",
        )

    def handle(self, *args, **options):
        schema = options.get("schema")
        all_tenants = options.get("all_tenants")
        create_missing_classes = options.get("create_missing_classes")
        fix_class_metadata = options.get("fix_class_metadata")

        if schema and all_tenants:
            raise CommandError("Use either --schema or --all-tenants, not both.")

        if not schema and not all_tenants:
            raise CommandError(
                "Please provide --schema demo or use --all-tenants."
            )

        if all_tenants:
            schemas = list(
                School.objects.exclude(schema_name="public")
                .values_list("schema_name", flat=True)
            )
        else:
            schemas = [schema]

        for schema_name in schemas:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"Seeding tenant: {schema_name}"))

            with schema_context(schema_name):
                self.seed_schema(
                    schema_name=schema_name,
                    create_missing_classes=create_missing_classes,
                    fix_class_metadata=fix_class_metadata,
                )

    @transaction.atomic
    def seed_schema(
        self,
        schema_name,
        create_missing_classes=False,
        fix_class_metadata=False,
    ):
        created_subjects = 0
        updated_subjects = 0
        created_classes = 0
        updated_classes = 0
        assignments = 0
        skipped_classes = []

        for class_name, learning_areas in CLASS_LEARNING_AREA_MAP.items():
            class_obj, class_created, class_updated = self.get_or_create_class(
                class_name=class_name,
                create_missing_classes=create_missing_classes,
                fix_class_metadata=fix_class_metadata,
            )

            if class_created:
                created_classes += 1

            if class_updated:
                updated_classes += 1

            if not class_obj:
                skipped_classes.append(class_name)
                continue

            for item in learning_areas:
                subject, subject_created, subject_updated = self.get_or_create_subject(
                    name=item["name"],
                    code=item["code"],
                    result_code=item["result_code"],
                    order=item["order"],
                )

                if subject_created:
                    created_subjects += 1

                if subject_updated:
                    updated_subjects += 1

                before_count = subject.applicable_classes.count()
                subject.applicable_classes.add(class_obj)
                after_count = subject.applicable_classes.count()

                if after_count > before_count:
                    assignments += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{schema_name}: created_classes={created_classes}, "
                f"updated_classes={updated_classes}, "
                f"created_subjects={created_subjects}, "
                f"updated_subjects={updated_subjects}, "
                f"class_subject_assignments={assignments}"
            )
        )

        if skipped_classes:
            self.stdout.write(
                self.style.WARNING(
                    f"{schema_name}: skipped missing classes: "
                    + ", ".join(skipped_classes)
                )
            )

        self.print_class_subject_counts(schema_name)

    def get_or_create_class(
        self,
        class_name,
        create_missing_classes=False,
        fix_class_metadata=False,
    ):
        class_obj = Class.objects.filter(name__iexact=class_name).first()

        if not class_obj:
            if not create_missing_classes:
                return None, False, False

            class_defaults = CBC_CLASS_DEFINITIONS[class_name].copy()

            class_obj = Class.objects.create(
                name=class_name,
                code=class_name.upper().replace(" ", "_"),
                **class_defaults,
            )

            return class_obj, True, False

        updated = False

        if fix_class_metadata:
            metadata = CBC_CLASS_DEFINITIONS[class_name]

            for field_name, value in metadata.items():
                if hasattr(class_obj, field_name):
                    current_value = getattr(class_obj, field_name)

                    if current_value != value:
                        setattr(class_obj, field_name, value)
                        updated = True

            if not class_obj.code:
                class_obj.code = class_name.upper().replace(" ", "_")
                updated = True

            if updated:
                class_obj.save()

        return class_obj, False, updated

    def get_or_create_subject(self, name, code, result_code, order):
        subject = Subject.objects.filter(name__iexact=name).first()

        if not subject:
            subject = Subject.objects.filter(code__iexact=code).first()

        if not subject:
            subject = Subject.objects.create(
                name=name,
                code=code,
                result_code=result_code,
                category="compulsory",
                is_compulsory=True,
                is_active=True,
                order=order,
            )

            return subject, True, False

        updated = False

        if not subject.code:
            subject.code = code
            updated = True

        if subject.result_code is None:
            subject.result_code = result_code
            updated = True

        if subject.category != "compulsory":
            subject.category = "compulsory"
            updated = True

        if not subject.is_compulsory:
            subject.is_compulsory = True
            updated = True

        if not subject.is_active:
            subject.is_active = True
            updated = True

        if not subject.order:
            subject.order = order
            updated = True

        if updated:
            subject.save()

        return subject, False, updated

    def print_class_subject_counts(self, schema_name):
        self.stdout.write("")
        self.stdout.write(f"{schema_name}: Grade 1 to Grade 9 subject counts")

        for class_name in CLASS_LEARNING_AREA_MAP.keys():
            class_obj = Class.objects.filter(name__iexact=class_name).first()

            if not class_obj:
                self.stdout.write(f"  {class_name}: class missing")
                continue

            count = Subject.objects.filter(
                applicable_classes=class_obj,
                is_active=True,
            ).distinct().count()

            self.stdout.write(f"  {class_name}: {count} learning areas")
