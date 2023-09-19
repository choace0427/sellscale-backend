# What does this script do?
#  - Moves a client SDR and all of their respective objects to the graveyard client
#  - This is useful for when a client SDR leaves the company
#  - This is also useful for when a client SDR is no longer working on a client
#  - This is also useful for when a client SDR is no longer working on a client archetype


exec(
    """
def refresh_sdr():
    try:
        from model_import import Prospect, ClientArchetype, ClientSDR, PhantomBusterConfig, DemoFeedback, StackRankedMessageGenerationConfiguration, ProspectUploadsRawCSV, ProspectUploads, VoiceBuilderOnboarding
        from tqdm import tqdm
            
        OLD_CLIENT_SDR_ID = 71
        NEW_CLIENT_ID = 48 # graveyard client ID

        client_sdr = ClientSDR.query.get(OLD_CLIENT_SDR_ID)
        prospects = Prospect.query.filter(
            Prospect.client_sdr_id == OLD_CLIENT_SDR_ID, Prospect.client_id != NEW_CLIENT_ID
        ).all()
        archetypes = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == OLD_CLIENT_SDR_ID, ClientArchetype.client_id != NEW_CLIENT_ID
        ).all()
        pb_configs = PhantomBusterConfig.query.filter(
            PhantomBusterConfig.client_sdr_id == OLD_CLIENT_SDR_ID, PhantomBusterConfig.client_id != NEW_CLIENT_ID
        ).all()
        demo_feedbacks = DemoFeedback.query.filter(
            DemoFeedback.client_sdr_id == OLD_CLIENT_SDR_ID, DemoFeedback.client_id != NEW_CLIENT_ID
        ).all()
        stack_ranked_message_generation_configs = StackRankedMessageGenerationConfiguration.query.filter(
            StackRankedMessageGenerationConfiguration.archetype_id.in_([archetype.id for archetype in archetypes]), StackRankedMessageGenerationConfiguration.client_id != NEW_CLIENT_ID
        ).all()
        prospect_uploads_raw_csvs = ProspectUploadsRawCSV.query.filter(
            ProspectUploadsRawCSV.client_sdr_id == OLD_CLIENT_SDR_ID, ProspectUploadsRawCSV.client_id != NEW_CLIENT_ID
        ).all()
        prospect_uploads = ProspectUploads.query.filter(
            ProspectUploads.client_sdr_id == OLD_CLIENT_SDR_ID, ProspectUploads.client_id != NEW_CLIENT_ID
        ).all()
        voice_builder_onboardings = VoiceBuilderOnboarding.query.filter(
            VoiceBuilderOnboarding.client_archetype_id.in_([archetype.id for archetype in archetypes]), VoiceBuilderOnboarding.client_id != NEW_CLIENT_ID
        ).all()


        print("Client SDR: ", client_sdr)
        print(str(len(prospects)), " prospects")
        print(str(len(archetypes)), " archetypes")
        print(str(len(pb_configs)), " pb configs")
        print(str(len(demo_feedbacks)), " demo feedbacks")
        print(str(len(stack_ranked_message_generation_configs)), " stack ranked message generation configs")
        print(str(len(prospect_uploads_raw_csvs)), " prospect uploads raw csvs")
        print(str(len(prospect_uploads)), " prospect uploads")
        print(str(len(voice_builder_onboardings)), " voice builder onboardings")

        print("Updating archetypes...")
        for archetype in tqdm(archetypes):
            archetype.client_id = NEW_CLIENT_ID
            db.session.add(archetype)
            db.session.commit()

        print("Updating prospects...")
        count = 0
        for prospect in tqdm(prospects):
            count += 1
            prospect.client_id = NEW_CLIENT_ID
            db.session.add(prospect)
            db.session.commit()
            
        print("Updating pb configs...")
        for pb_config in tqdm(pb_configs):
            pb_config.client_id = NEW_CLIENT_ID
            db.session.add(pb_config)
            db.session.commit()

        print("Updating demo feedbacks...")
        for demo_feedback in tqdm(demo_feedbacks):
            demo_feedback.client_id = NEW_CLIENT_ID
            db.session.add(demo_feedback)
            db.session.commit()
            
        print("Updating stack ranked message generation configs...")
        for stack_ranked_message_generation_config in tqdm(stack_ranked_message_generation_configs):
            stack_ranked_message_generation_config.client_id = NEW_CLIENT_ID
            db.session.add(stack_ranked_message_generation_config)
            db.session.commit()

        print("Updating prospect uploads raw csvs...")
        for prospect_uploads_raw_csv in tqdm(prospect_uploads_raw_csvs):
            prospect_uploads_raw_csv.client_id = NEW_CLIENT_ID
            db.session.add(prospect_uploads_raw_csv)
            db.session.commit()
            
        print("Updating prospect uploads...")
        for prospect_upload in tqdm(prospect_uploads):
            prospect_upload.client_id = NEW_CLIENT_ID
            db.session.add(prospect_upload)
            db.session.commit()
            
        print("Updating voice builder onboardings...")
        for voice_builder_onboarding in tqdm(voice_builder_onboardings):
            voice_builder_onboarding.client_id = NEW_CLIENT_ID
            db.session.add(voice_builder_onboarding)w
            db.session.commit()
     
        client_sdr.client_id = NEW_CLIENT_ID
            
        print("Done!")
        return True
    except Exception as e:
        print(e)
        return False
     
continue_loop = True
while continue_loop:
    continue_loop = refresh_sdr()
"""
)
