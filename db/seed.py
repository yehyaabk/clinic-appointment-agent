from db.config import get_connection

SEED_DOCTORS = [
    {"full_name": "Dr. Sophie Martin", "specialization": "Dermatology", "years_experience": 12,
     "description": "Specializes in skin conditions, allergies, and acne treatment."},
    {"full_name": "Dr. Karim Belhadj", "specialization": "Dermatology", "years_experience": 8,
     "description": "Treats chronic skin disorders, eczema, and psoriasis."},
    {"full_name": "Dr. Amélie Rousseau", "specialization": "Dermatology", "years_experience": 6,
     "description": "Focuses on pediatric dermatology and skin allergy testing."},

    {"full_name": "Dr. Jean-Paul Dupont", "specialization": "Cardiology", "years_experience": 20,
     "description": "Specializes in heart disease prevention and management."},
    {"full_name": "Dr. Nadia Benali", "specialization": "Cardiology", "years_experience": 14,
     "description": "Focuses on hypertension management and cardiac rehabilitation."},
    {"full_name": "Dr. Laurent Girard", "specialization": "Cardiology", "years_experience": 9,
     "description": "Specializes in arrhythmia diagnosis and echocardiography."},

    {"full_name": "Dr. Amel Cherif", "specialization": "General Medicine", "years_experience": 15,
     "description": "General practitioner for everyday health concerns and check-ups."},
    {"full_name": "Dr. Thomas Lambert", "specialization": "General Medicine", "years_experience": 11,
     "description": "Provides routine care, vaccinations, and referrals to specialists."},
    {"full_name": "Dr. Claire Fontaine", "specialization": "General Medicine", "years_experience": 7,
     "description": "Focuses on preventive medicine and chronic disease follow-up."},

    {"full_name": "Dr. Marie Lefevre", "specialization": "Pediatrics", "years_experience": 10,
     "description": "Specializes in the health and development of infants and children."},
    {"full_name": "Dr. Hugo Moreau", "specialization": "Pediatrics", "years_experience": 13,
     "description": "Focuses on childhood vaccinations and growth monitoring."},

    {"full_name": "Dr. Isabelle Faure", "specialization": "Gynecology", "years_experience": 18,
     "description": "Specializes in women's reproductive health and prenatal care."},
    {"full_name": "Dr. Camille Perrin", "specialization": "Gynecology", "years_experience": 9,
     "description": "Focuses on gynecological screenings and fertility consultations."},

    {"full_name": "Dr. Antoine Roche", "specialization": "Ophthalmology", "years_experience": 16,
     "description": "Specializes in cataract diagnosis and vision correction."},
    {"full_name": "Dr. Julie Bertrand", "specialization": "Ophthalmology", "years_experience": 5,
     "description": "Focuses on pediatric eye exams and glaucoma screening."},

    {"full_name": "Dr. Pierre Lambert", "specialization": "Orthopedics", "years_experience": 22,
     "description": "Specializes in joint injuries and post-surgical rehabilitation."},
    {"full_name": "Dr. Emma Dubois", "specialization": "Orthopedics", "years_experience": 10,
     "description": "Focuses on sports injuries and fracture treatment."},

    {"full_name": "Dr. Mehdi Saidi", "specialization": "General Medicine", "years_experience": 4,
     "description": "Provides general consultations and minor injury care."},
    {"full_name": "Dr. Lucie Marchand", "specialization": "Cardiology", "years_experience": 3,
     "description": "Focuses on cardiovascular risk assessment for younger patients."},
    {"full_name": "Dr. Nicolas Bonnet", "specialization": "Dermatology", "years_experience": 17,
     "description": "Specializes in skin cancer screening and mole examination."},
]


def seed_doctors():
    """
    Adds any doctors from SEED_DOCTORS that don't already exist in the
    database (matched by full_name). Safe to call on every app startup —
    existing doctors are never duplicated, and only genuinely new entries
    are inserted and counted.
    """
    connection = get_connection()
    cursor = connection.cursor()

    new_count = 0

    for doctor in SEED_DOCTORS:
        cursor.execute("SELECT id FROM doctors WHERE full_name = %s", (doctor["full_name"],))
        if cursor.fetchone() is not None:
            continue  # already exists, skip

        cursor.execute(
            """INSERT INTO doctors (full_name, specialization, years_experience, description)
               VALUES (%s, %s, %s, %s)""",
            (doctor["full_name"], doctor["specialization"], doctor["years_experience"], doctor["description"])
        )
        new_count += 1

    connection.commit()
    cursor.close()
    connection.close()

    print(f"{new_count} new doctor(s) added.")