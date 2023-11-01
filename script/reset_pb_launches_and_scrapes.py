from app import db
from model_import import (
    PhantomBusterSalesNavigatorConfig,
    PhantomBusterSalesNavigatorLaunch,
)
import datetime

# from PhantomBusterSalesNavigatorConfig, pick things are still `in_use` and have been there for more than 15 minutes
configs: PhantomBusterSalesNavigatorConfig = (
    db.session.query(PhantomBusterSalesNavigatorConfig)
    .filter(PhantomBusterSalesNavigatorConfig.in_use == True)
    .filter(
        PhantomBusterSalesNavigatorConfig.updated_at
        < datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
    )
    .all()
)
for config in configs:
    config.in_use = False
    config.daily_trigger_count = 0
    config.daily_prospect_count = 0
    print("Resetting config #", config.id)
    db.session.add(config)
    db.session.commit()

# if something has been in QUEUED, RUNNING, NEEDS_AGENT, for more than 15 minutes, then we can assume it's stuck and we should reset it
launches = (
    db.session.query(PhantomBusterSalesNavigatorLaunch)
    .filter(
        PhantomBusterSalesNavigatorLaunch.status.in_(
            ["QUEUED", "RUNNING", "NEEDS_AGENT"]
        )
    )
    .filter(
        PhantomBusterSalesNavigatorLaunch.updated_at
        < datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
    )
    .all()
)
for launch in launches:
    launch.status = "QUEUED"
    launch.error_message = None
    launch.launch_date = None
    print("Resetting launch #", launch.id)
    db.session.add(launch)
    db.session.commit()
