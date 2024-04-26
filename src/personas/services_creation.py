from model_import import (
    EmailSequenceStep,
    EmailSubjectLineTemplate,
    ClientArchetype,
    ProspectOverallStatus,
    GeneratedMessageCTA,
    BumpFramework,
    GeneratedMessageCTAToAssetMapping,
    EmailSequenceStepToAssetMapping,
)
from src.bump_framework.models import BumpFrameworkToAssetMapping, BumpLength
from src.li_conversation.models import (
    LinkedInInitialMessageToAssetMapping,
    LinkedinInitialMessageTemplate,
)
from app import db
from src.email_sequencing.services import (
    create_email_sequence_step,
    create_email_subject_line_template,
    delete_email_sequence_step_asset_mapping,
)
from src.client.archetype.services_client_archetype import (
    create_linkedin_initial_message_template,
    delete_li_init_template_asset_mapping,
)
from src.message_generation.services import (
    delete_cta,
    create_cta,
    delete_cta_asset_mapping,
)
from src.bump_framework.services import (
    create_bump_framework,
    delete_bump_framework_asset_mapping,
)


def add_sequence(
    client_id, archetype_id, sequence_type, subject_lines, steps, override=False
):

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)

    if sequence_type == "EMAIL":

        # Wipe the existing sequence steps
        if override:
            sequence_steps = EmailSequenceStep.query.filter_by(
                client_archetype_id=archetype_id
            ).all()

            for step in sequence_steps:
                mappings = EmailSequenceStepToAssetMapping.query.filter_by(
                    email_sequence_step_id=step.id
                ).all()
                for mapping in mappings:
                    delete_email_sequence_step_asset_mapping(mapping.id)
                db.session.delete(step)
            db.session.commit()

        # Add the new sequence steps
        for i, step in enumerate(steps):

            template = step["text"]
            # replace all \n with <br> for the email template
            template = template.replace("\n", "<br>")

            create_email_sequence_step(
                client_sdr_id=archetype.client_sdr_id,
                client_archetype_id=archetype_id,
                title=step["angle"],
                template=template,
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
        if override:
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
        if override:
            ctas = GeneratedMessageCTA.query.filter_by(archetype_id=archetype_id).all()

            for cta in ctas:
                mappings = GeneratedMessageCTAToAssetMapping.query.filter_by(
                    generated_message_cta_id=cta.id
                ).all()
                for mapping in mappings:
                    delete_cta_asset_mapping(mapping.id)
                delete_cta(cta.id)

        # Add the new CTAs
        for i, cta_input in enumerate(subject_lines):
            create_cta(
                archetype_id=archetype_id,
                text_value=cta_input["text"],
                asset_ids=cta_input["assets"],
                expiration_date=None,
            )

    elif sequence_type == "LINKEDIN-TEMPLATE":

        # Wipe the existing initial messages
        if override:
            linkedin_initial_messages = LinkedinInitialMessageTemplate.query.filter_by(
                client_archetype_id=archetype_id
            ).all()

            for message in linkedin_initial_messages:
                mappings = LinkedInInitialMessageToAssetMapping.query.filter_by(
                    linkedin_initial_message_id=message.id
                ).all()
                for mapping in mappings:
                    delete_li_init_template_asset_mapping(mapping.id)
                db.session.delete(message)
            db.session.commit()

        # Add the new initial messages
        for i, step in enumerate(steps):
            if step["step_num"] != 1:
                continue
            create_linkedin_initial_message_template(
                title=step["angle"],
                message=step["text"],
                client_sdr_id=archetype.client_sdr_id,
                client_archetype_id=archetype_id,
                research_points=[],
                additional_instructions="",
                asset_ids=step["assets"],
            )

    if sequence_type.startswith("LINKEDIN-"):

        # Update the archetype template mode
        archetype.template_mode = (
            True if sequence_type == "LINKEDIN-TEMPLATE" else False
        )
        archetype.li_bump_amount = max(step["step_num"] for step in steps) - 1
        db.session.commit()

        # Wipe the existing bump frameworks
        if override:
            bumps = BumpFramework.query.filter_by(
                client_archetype_id=archetype_id
            ).all()

            for bump in bumps:
                mappings = BumpFrameworkToAssetMapping.query.filter_by(
                    bump_framework_id=bump.id
                ).all()
                for mapping in mappings:
                    delete_bump_framework_asset_mapping(mapping.id)
                db.session.delete(bump)
            db.session.commit()

        # Add the new sequence steps
        for i, step in enumerate(steps):
            if step["step_num"] == 1:
                continue
            id = create_bump_framework(
                client_sdr_id=archetype.client_sdr_id,
                client_archetype_id=archetype_id,
                title=step["angle"],
                description=step["text"],
                overall_status=(
                    ProspectOverallStatus.ACCEPTED
                    if step["step_num"] == 2
                    else ProspectOverallStatus.BUMPED
                ),
                length=BumpLength.MEDIUM,
                additional_instructions="",
                bumped_count=(step["step_num"] - 2),
                asset_ids=step["assets"],
                active=True,
                default=True,
            )

    return True
