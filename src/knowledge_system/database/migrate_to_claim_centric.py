"""
Migration script: Old HCE schema → Claim-Centric schema

This script migrates from the old episode-centric HCE schema to the new
claim-centric architecture where claims are the fundamental unit.
"""

import json
import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def migrate_to_claim_centric(old_db_path: Path, new_db_path: Path) -> None:
    """
    Migrate from old HCE schema to claim-centric schema.
    
    Args:
        old_db_path: Path to old database
        new_db_path: Path to new database (will be created)
    """
    logger.info("=" * 80)
    logger.info("MIGRATING TO CLAIM-CENTRIC SCHEMA")
    logger.info("=" * 80)
    
    # Connect to old database
    old_engine = create_engine(f"sqlite:///{old_db_path}")
    OldSession = sessionmaker(bind=old_engine)
    old_session = OldSession()
    
    # Create new database with claim-centric schema
    new_engine = create_engine(f"sqlite:///{new_db_path}")
    
    # Load schema
    schema_file = Path(__file__).parent / "migrations" / "claim_centric_schema.sql"
    with open(schema_file) as f:
        schema_sql = f.read()
    
    # Execute schema (split by statements)
    with new_engine.connect() as conn:
        # Execute each statement separately
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    conn.execute(text(statement))
                except Exception as e:
                    if 'already exists' not in str(e):
                        logger.error(f"Error executing statement: {e}")
        conn.commit()
    
    NewSession = sessionmaker(bind=new_engine)
    new_session = NewSession()
    
    try:
        # === 1. Migrate media_sources ===
        logger.info("\n1. Migrating media sources...")
        
        # From old 'videos' or 'media_sources' table
        old_sources = old_session.execute(text("""
            SELECT 
                media_id, title, url, description,
                uploader, uploader_id, upload_date,
                duration_seconds, view_count, like_count
            FROM media_sources
        """)).fetchall()
        
        for row in old_sources:
            new_session.execute(text("""
                INSERT OR REPLACE INTO media_sources (
                    source_id, source_type, title, url, description,
                    uploader, uploader_id, upload_date,
                    duration_seconds, view_count, like_count
                ) VALUES (
                    :media_id, 'episode', :title, :url, :description,
                    :uploader, :uploader_id, :upload_date,
                    :duration, :views, :likes
                )
            """), {
                'media_id': row[0],
                'title': row[1],
                'url': row[2],
                'description': row[3],
                'uploader': row[4],
                'uploader_id': row[5],
                'upload_date': row[6],
                'duration': row[7],
                'views': row[8],
                'likes': row[9],
            })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(old_sources)} media sources")
        
        # === 2. Migrate episodes ===
        logger.info("\n2. Migrating episodes...")
        
        old_episodes = old_session.execute(text("""
            SELECT episode_id, video_id, title, recorded_at
            FROM hce_episodes
        """)).fetchall()
        
        for row in old_episodes:
            episode_id, video_id, title, recorded_at = row
            
            # Create episode linked to source
            new_session.execute(text("""
                INSERT OR REPLACE INTO episodes (
                    episode_id, source_id, title, recorded_at
                ) VALUES (
                    :episode_id, :source_id, :title, :recorded_at
                )
            """), {
                'episode_id': episode_id,
                'source_id': video_id,
                'title': title,
                'recorded_at': recorded_at,
            })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(old_episodes)} episodes")
        
        # === 3. Migrate segments ===
        logger.info("\n3. Migrating segments...")
        
        old_segments = old_session.execute(text("""
            SELECT episode_id, segment_id, speaker, t0, t1, text
            FROM hce_segments
        """)).fetchall()
        
        for i, row in enumerate(old_segments):
            episode_id, segment_id, speaker, t0, t1, text = row
            
            new_session.execute(text("""
                INSERT OR REPLACE INTO segments (
                    segment_id, episode_id, speaker, start_time, end_time, text, sequence
                ) VALUES (
                    :segment_id, :episode_id, :speaker, :t0, :t1, :text, :seq
                )
            """), {
                'segment_id': segment_id,
                'episode_id': episode_id,
                'speaker': speaker,
                't0': t0,
                't1': t1,
                'text': text,
                'seq': i,
            })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(old_segments)} segments")
        
        # === 4. Migrate claims (WITH GLOBAL IDs) ===
        logger.info("\n4. Migrating claims to claim-centric model...")
        
        old_claims = old_session.execute(text("""
            SELECT 
                episode_id, claim_id, canonical, claim_type, tier,
                first_mention_ts, scores_json,
                temporality_score, temporality_confidence, temporality_rationale
            FROM hce_claims
        """)).fetchall()
        
        for row in old_claims:
            episode_id, claim_id, canonical, claim_type, tier, first_mention, scores_json, temp_score, temp_conf, temp_rationale = row
            
            # Generate global claim ID
            source_id = episode_id.replace("episode_", "")
            global_claim_id = f"{source_id}_{claim_id}"
            
            # Parse scores JSON
            scores = json.loads(scores_json) if scores_json else {}
            
            new_session.execute(text("""
                INSERT OR REPLACE INTO claims (
                    claim_id, source_id, episode_id,
                    canonical, claim_type, tier,
                    importance_score, specificity_score, verifiability_score,
                    first_mention_ts,
                    temporality_score, temporality_confidence, temporality_rationale
                ) VALUES (
                    :claim_id, :source_id, :episode_id,
                    :canonical, :claim_type, :tier,
                    :importance, :specificity, :verifiability,
                    :first_mention,
                    :temp_score, :temp_conf, :temp_rationale
                )
            """), {
                'claim_id': global_claim_id,
                'source_id': source_id,
                'episode_id': episode_id,
                'canonical': canonical,
                'claim_type': claim_type,
                'tier': tier,
                'importance': scores.get('importance'),
                'specificity': scores.get('specificity'),
                'verifiability': scores.get('verifiability'),
                'first_mention': first_mention,
                'temp_score': temp_score,
                'temp_conf': temp_conf,
                'temp_rationale': temp_rationale,
            })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(old_claims)} claims with global IDs")
        
        # === 5. Migrate evidence spans ===
        logger.info("\n5. Migrating evidence spans...")
        
        old_evidence = old_session.execute(text("""
            SELECT 
                episode_id, claim_id, seq, segment_id,
                t0, t1, quote,
                context_t0, context_t1, context_text, context_type
            FROM hce_evidence_spans
        """)).fetchall()
        
        for row in old_evidence:
            episode_id, claim_id, seq, segment_id, t0, t1, quote, ctx_t0, ctx_t1, ctx_text, ctx_type = row
            
            # Generate global claim ID
            source_id = episode_id.replace("episode_", "")
            global_claim_id = f"{source_id}_{claim_id}"
            
            new_session.execute(text("""
                INSERT INTO evidence_spans (
                    claim_id, segment_id, sequence,
                    start_time, end_time, quote,
                    context_start_time, context_end_time, context_text, context_type
                ) VALUES (
                    :claim_id, :segment_id, :seq,
                    :t0, :t1, :quote,
                    :ctx_t0, :ctx_t1, :ctx_text, :ctx_type
                )
            """), {
                'claim_id': global_claim_id,
                'segment_id': segment_id,
                'seq': seq,
                't0': t0,
                't1': t1,
                'quote': quote,
                'ctx_t0': ctx_t0,
                'ctx_t1': ctx_t1,
                'ctx_text': ctx_text,
                'ctx_type': ctx_type,
            })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(old_evidence)} evidence spans")
        
        # === 6. Migrate claim relations ===
        logger.info("\n6. Migrating claim relations...")
        
        old_relations = old_session.execute(text("""
            SELECT episode_id, source_claim_id, target_claim_id, type, strength, rationale
            FROM hce_relations
        """)).fetchall()
        
        for row in old_relations:
            episode_id, source_claim_id, target_claim_id, rel_type, strength, rationale = row
            
            # Generate global claim IDs
            source_id = episode_id.replace("episode_", "")
            global_source_id = f"{source_id}_{source_claim_id}"
            global_target_id = f"{source_id}_{target_claim_id}"
            
            new_session.execute(text("""
                INSERT OR IGNORE INTO claim_relations (
                    source_claim_id, target_claim_id, relation_type, strength, rationale
                ) VALUES (
                    :source_id, :target_id, :type, :strength, :rationale
                )
            """), {
                'source_id': global_source_id,
                'target_id': global_target_id,
                'type': rel_type,
                'strength': strength,
                'rationale': rationale,
            })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(old_relations)} claim relations")
        
        # === 7. Migrate people (denormalized → normalized) ===
        logger.info("\n7. Migrating people...")
        
        old_people = old_session.execute(text("""
            SELECT 
                episode_id, person_id, name, normalized, description,
                entity_type, external_ids_json, confidence, first_mention_ts
            FROM hce_people
        """)).fetchall()
        
        person_map = {}  # Track person_id mappings
        
        for row in old_people:
            episode_id, person_id, name, normalized, description, entity_type, ext_ids_json, confidence, first_mention = row
            
            normalized_name = normalized or name
            
            # Check if person already exists
            if normalized_name not in person_map:
                # Create new person
                new_person_id = f"person_{normalized_name.replace(' ', '_').lower()}"
                
                new_session.execute(text("""
                    INSERT OR IGNORE INTO people (
                        person_id, name, normalized_name, description, entity_type, confidence
                    ) VALUES (
                        :person_id, :name, :normalized, :description, :entity_type, :confidence
                    )
                """), {
                    'person_id': new_person_id,
                    'name': name,
                    'normalized': normalized_name,
                    'description': description,
                    'entity_type': entity_type or 'person',
                    'confidence': confidence,
                })
                
                person_map[normalized_name] = new_person_id
                
                # Store external IDs (normalized)
                if ext_ids_json:
                    try:
                        external_ids = json.loads(ext_ids_json)
                        for system, ext_id in external_ids.items():
                            new_session.execute(text("""
                                INSERT OR IGNORE INTO person_external_ids (
                                    person_id, external_system, external_id
                                ) VALUES (:person_id, :system, :ext_id)
                            """), {
                                'person_id': new_person_id,
                                'system': system,
                                'ext_id': ext_id,
                            })
                    except json.JSONDecodeError:
                        pass
            
            # Link person to all claims in this episode
            # (This is approximate - would need NLP to determine exact claim-person links)
            source_id = episode_id.replace("episode_", "")
            new_person_id = person_map[normalized_name]
            
            # Get all claims for this episode
            claims = old_session.execute(text("""
                SELECT claim_id FROM hce_claims WHERE episode_id = :episode_id
            """), {'episode_id': episode_id}).fetchall()
            
            for claim_row in claims:
                claim_id = claim_row[0]
                global_claim_id = f"{source_id}_{claim_id}"
                
                new_session.execute(text("""
                    INSERT OR IGNORE INTO claim_people (
                        claim_id, person_id, first_mention_ts
                    ) VALUES (:claim_id, :person_id, :first_mention)
                """), {
                    'claim_id': global_claim_id,
                    'person_id': new_person_id,
                    'first_mention': first_mention,
                })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(person_map)} unique people")
        
        # === 8. Migrate concepts ===
        logger.info("\n8. Migrating concepts...")
        
        old_concepts = old_session.execute(text("""
            SELECT 
                episode_id, concept_id, name, definition,
                first_mention_ts, aliases_json
            FROM hce_concepts
        """)).fetchall()
        
        concept_map = {}
        
        for row in old_concepts:
            episode_id, concept_id, name, definition, first_mention, aliases_json = row
            
            if name not in concept_map:
                new_concept_id = f"concept_{name.replace(' ', '_').lower()}"
                
                new_session.execute(text("""
                    INSERT OR IGNORE INTO concepts (
                        concept_id, name, definition
                    ) VALUES (:concept_id, :name, :definition)
                """), {
                    'concept_id': new_concept_id,
                    'name': name,
                    'definition': definition,
                })
                
                concept_map[name] = new_concept_id
                
                # Store aliases (normalized)
                if aliases_json:
                    try:
                        aliases = json.loads(aliases_json)
                        for alias in aliases:
                            new_session.execute(text("""
                                INSERT OR IGNORE INTO concept_aliases (
                                    concept_id, alias
                                ) VALUES (:concept_id, :alias)
                            """), {
                                'concept_id': new_concept_id,
                                'alias': alias,
                            })
                    except json.JSONDecodeError:
                        pass
            
            # Link concept to claims in this episode
            source_id = episode_id.replace("episode_", "")
            new_concept_id = concept_map[name]
            
            claims = old_session.execute(text("""
                SELECT claim_id FROM hce_claims WHERE episode_id = :episode_id
            """), {'episode_id': episode_id}).fetchall()
            
            for claim_row in claims:
                claim_id = claim_row[0]
                global_claim_id = f"{source_id}_{claim_id}"
                
                new_session.execute(text("""
                    INSERT OR IGNORE INTO claim_concepts (
                        claim_id, concept_id, first_mention_ts
                    ) VALUES (:claim_id, :concept_id, :first_mention)
                """), {
                    'claim_id': global_claim_id,
                    'concept_id': new_concept_id,
                    'first_mention': first_mention,
                })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(concept_map)} unique concepts")
        
        # === 9. Migrate jargon ===
        logger.info("\n9. Migrating jargon...")
        
        old_jargon = old_session.execute(text("""
            SELECT 
                episode_id, term_id, term, definition, category, first_mention_ts
            FROM hce_jargon
        """)).fetchall()
        
        jargon_map = {}
        
        for row in old_jargon:
            episode_id, term_id, term, definition, category, first_mention = row
            
            if term not in jargon_map:
                new_jargon_id = f"jargon_{term.replace(' ', '_').lower()}"
                
                new_session.execute(text("""
                    INSERT OR IGNORE INTO jargon_terms (
                        jargon_id, term, definition, domain
                    ) VALUES (:jargon_id, :term, :definition, :domain)
                """), {
                    'jargon_id': new_jargon_id,
                    'term': term,
                    'definition': definition,
                    'domain': category,
                })
                
                jargon_map[term] = new_jargon_id
            
            # Link jargon to claims
            source_id = episode_id.replace("episode_", "")
            new_jargon_id = jargon_map[term]
            
            claims = old_session.execute(text("""
                SELECT claim_id FROM hce_claims WHERE episode_id = :episode_id
            """), {'episode_id': episode_id}).fetchall()
            
            for claim_row in claims:
                claim_id = claim_row[0]
                global_claim_id = f"{source_id}_{claim_id}"
                
                new_session.execute(text("""
                    INSERT OR IGNORE INTO claim_jargon (
                        claim_id, jargon_id, first_mention_ts
                    ) VALUES (:claim_id, :jargon_id, :first_mention)
                """), {
                    'claim_id': global_claim_id,
                    'jargon_id': new_jargon_id,
                    'first_mention': first_mention,
                })
        
        new_session.commit()
        logger.info(f"✅ Migrated {len(jargon_map)} unique jargon terms")
        
        # === 10. Summary ===
        logger.info("\n" + "=" * 80)
        logger.info("MIGRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Old database: {old_db_path}")
        logger.info(f"New database: {new_db_path}")
        logger.info("")
        logger.info("New schema is claim-centric:")
        logger.info("  - Claims have global unique IDs")
        logger.info("  - Claims reference sources (not vice versa)")
        logger.info("  - People, concepts, jargon are normalized")
        logger.info("  - No JSON fields - everything is queryable")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Load WikiData vocabulary: python -m src.knowledge_system.database.load_wikidata_vocab")
        logger.info("  2. Test queries against new schema")
        logger.info("  3. Update application code to use ClaimStore")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        new_session.rollback()
        raise
    finally:
        old_session.close()
        new_session.close()


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 3:
        print("Usage: python migrate_to_claim_centric.py <old_db_path> <new_db_path>")
        sys.exit(1)
    
    old_db = Path(sys.argv[1])
    new_db = Path(sys.argv[2])
    
    if not old_db.exists():
        print(f"Error: Old database not found: {old_db}")
        sys.exit(1)
    
    if new_db.exists():
        response = input(f"New database {new_db} already exists. Overwrite? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled")
            sys.exit(0)
        new_db.unlink()
    
    migrate_to_claim_centric(old_db, new_db)

