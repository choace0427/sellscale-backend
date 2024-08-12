exec("""
from model_import import *
from app import db
     
CLIENT_IDS = [122, 119, 121, 120, 118, 115, 113, 111, 108, 106, 107, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 93]
for client_id in CLIENT_IDS:
    print(f"Deleting client_id: {client_id}")
    c = Client.query.get(client_id)
    if not c:
        continue
    cas = ClientArchetype.query.filter(ClientArchetype.client_id == client_id).all()
    bump_frameworks = BumpFramework.query.filter(BumpFramework.client_archetype_id.in_([ca.id for ca in cas])).all()
    icp_scoring_ruleset = ICPScoringRuleset.query.filter(ICPScoringRuleset.client_archetype_id.in_([ca.id for ca in cas])).all()
    ai_researchers = AIResearcher.query.filter(AIResearcher.client_id == client_id).all()
    strategies = Strategies.query.filter(Strategies.client_id == client_id).all()
        
    for s in strategies:
        db.session.delete(s)
        db.session.commit()
        
    for air in ai_researchers:
        db.session.delete(air)
        db.session.commit()
        
    for icp in icp_scoring_ruleset:
        db.session.delete(icp)
        db.session.commit()
        
    for bf in bump_frameworks:
        db.session.delete(bf)
        db.session.commit()

    for ca in cas:
        db.session.delete(ca)
        db.session.commit()
        
    db.session.delete(c)
    db.session.commit()
""")