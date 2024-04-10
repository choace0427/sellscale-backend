from model_import import (
    EmailSequenceStep,
    EmailSubjectLineTemplate,
    ClientArchetype,
    ProspectOverallStatus,
    GeneratedMessageCTA,
)
from app import db
from src.email_sequencing.services import (
    create_email_sequence_step,
    create_email_subject_line_template,
)
from src.message_generation.services import delete_cta, create_cta


def add_sequence(client_id, archetype_id, sequence_type, ctas, subject_lines, steps):

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)

    print(client_id)
    print(archetype_id)
    print(sequence_type)
    print(ctas)
    print(subject_lines)

    if sequence_type == "EMAIL":

        # Wipe the existing sequence steps
        sequence_steps = EmailSequenceStep.query.filter_by(
            client_archetype_id=archetype_id
        ).all()

        for step in sequence_steps:
            db.session.delete(step)
        db.session.commit()

        # Add the new sequence steps
        for i, step in enumerate(steps):

            create_email_sequence_step(
                client_sdr_id=archetype.client_sdr_id,
                client_archetype_id=archetype_id,
                title="Imported Step",
                template=step["text"],
                overall_status=(
                    ProspectOverallStatus.PROSPECTED
                    if step["step_num"] == 1
                    else (
                        ProspectOverallStatus.ACCEPTED
                        if step["step_num"] == 2
                        else ProspectOverallStatus.BUMPED
                    )
                ),
                bumped_count=(
                    0
                    if step["step_num"] == 1
                    else (1 if step["step_num"] == 2 else step["step_num"] - 2)
                ),
                mapped_asset_ids=step["assets"],
                sellscale_default_generated=False,
            )

        # Wipe the existing subject lines
        subject_line_templates = EmailSubjectLineTemplate.query.filter_by(
            client_archetype_id=archetype_id
        ).all()

        for subject_line in subject_line_templates:
            db.session.delete(subject_line)
        db.session.commit()

        # Add the new subject lines
        for i, subject_line in enumerate(subject_lines):
            create_email_subject_line_template(
                client_sdr_id=archetype.client_sdr_id,
                client_archetype_id=archetype_id,
                subject_line=subject_line["text"],
                sellscale_generated=True,
            )

    elif sequence_type == "LINKEDIN-CTA":

        # Wipe the existing CTAs
        ctas = GeneratedMessageCTA.query.filter_by(archetype_id=archetype_id).all()

        for cta in ctas:
            delete_cta(cta.id)

        # Add the new CTAs
        for i, cta in enumerate(ctas):
            create_cta(
                archetype_id=archetype_id,
                text_value=cta["text"],
                asset_ids=cta["assets"],
            )

    else:
        pass
