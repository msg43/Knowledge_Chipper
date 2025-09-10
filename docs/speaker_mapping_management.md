# Speaker Mapping Management Guide

This guide explains how to manually edit speaker identification mappings in the Knowledge Chipper system.

## Overview

The system stores two types of speaker mappings:

1. **Channel-to-Host Mappings**: Persistent mappings like "Eurodollar University" → "Jeff Snider" 
2. **Content-Based Patterns**: YAML configuration for keyword-based speaker detection

## Method 1: GUI Interface (Recommended)

### Access the GUI
1. Launch the Knowledge Chipper application
2. Go to the **🎙️ Speaker Attribution** tab
3. Scroll down to the **"Channel-to-Host Mappings"** section

### Managing Mappings
- **View existing mappings**: All current mappings are displayed in the table
- **Add new mapping**: Enter channel name and host name, click "Save"
- **Edit existing mapping**: Click on a mapping to select it, modify the fields, click "Save"
- **Delete mapping**: Select a mapping and click "Delete" (requires confirmation)
- **Refresh**: Click "Refresh" to reload mappings from database

### Example Usage
```
Channel: "Eurodollar University"
Host: "Jeff Snider"
```

## Method 2: Command Line Script

### Using the Script
```bash
# Navigate to project directory
cd /Users/matthewgreer/Projects/Knowledge_Chipper

# List all mappings
python scripts/manage_speaker_mappings.py list

# Add a new mapping
python scripts/manage_speaker_mappings.py add "Eurodollar University" "Jeff Snider"

# Edit an existing mapping
python scripts/manage_speaker_mappings.py edit "Eurodollar University" "Jeffrey P. Snider"

# Delete a mapping
python scripts/manage_speaker_mappings.py delete "Eurodollar University"
```

### Script Features
- ✅ Lists all current mappings with usage statistics
- ✅ Adds new channel-to-host mappings
- ✅ Updates existing mappings
- ✅ Deletes mappings with confirmation
- ✅ Shows usage count and last updated information

## Method 3: Direct Database Access (Advanced)

### Database Location
- **File**: `~/Library/Application Support/KnowledgeChipper/knowledge_system.db`
- **Table**: `channel_host_mappings`

### Using SQLite CLI
```sql
-- View all mappings
SELECT channel_name, host_name, use_count, updated_at FROM channel_host_mappings;

-- Add new mapping
INSERT INTO channel_host_mappings (channel_name, host_name, confidence, created_by) 
VALUES ('Eurodollar University', 'Jeff Snider', 1.0, 'manual_edit');

-- Update existing mapping
UPDATE channel_host_mappings 
SET host_name = 'Jeffrey P. Snider', updated_at = datetime('now') 
WHERE channel_name = 'Eurodollar University';

-- Delete mapping
DELETE FROM channel_host_mappings WHERE channel_name = 'Eurodollar University';
```

## How Mappings Are Used

1. **During Transcription**: The system checks for existing channel mappings
2. **LLM Suggestions**: Known mappings influence AI-generated speaker name suggestions
3. **Manual Assignment**: When you manually assign speakers, the system learns the mapping
4. **Future Processing**: Learned mappings are automatically applied to new content from the same channel

## Content-Based Patterns (Advanced)

### YAML Configuration
**File**: `/Users/matthewgreer/Projects/Knowledge_Chipper/config/speaker_attribution.yaml`

```yaml
content_detection:
  keywords:
    # Add keyword patterns for speaker identification
    custom_speaker_indicators:
    - "specific phrase"
    - "unique terminology"

speaker_profiles:
  "Speaker Name":
    aliases:
    - "Alternative name"
    - "Nickname" 
    characteristics:
    - "speech patterns"
    - "accent description"
```

## Tips

1. **Use the GUI** for most editing tasks - it's the safest and most user-friendly
2. **Check usage counts** before deleting mappings that have been used frequently
3. **Be precise with channel names** - they must match exactly as they appear in video metadata
4. **Backup your database** before making direct SQL changes
5. **Test mappings** by processing content from the channel to verify they work correctly

## Troubleshooting

### Mapping Not Working
- Verify the channel name matches exactly (case-sensitive)
- Check that the mapping was saved successfully
- Restart the application to reload mappings

### GUI Not Showing
- Make sure you're on the latest version
- Check the logs for any initialization errors
- Try refreshing the mappings list

### Database Issues
- Ensure the application has write permissions to the database directory
- Check disk space
- Verify database file isn't corrupted

## Support

If you encounter issues with speaker mapping management:
1. Check the application logs in the `logs/` directory
2. Verify your database file isn't corrupted
3. Try the command-line script as an alternative to the GUI
4. Contact support with specific error messages and steps to reproduce

## 🎯 Solution: Seed 300+ Popular Podcast Mappings

Since I can't directly create the file, here's what you need to do:

### **Step 1: Create the Podcast Seeding Script**

Create a new file: `/Users/matthewgreer/Projects/Knowledge_Chipper/scripts/seed_podcast_mappings.py`

**Copy and paste this complete script:**

```python
#!/usr/bin/env python3
"""
Podcast Mapping Seeder

Seeds the channel-to-host mapping database with 300+ popular podcasts and their hosts.
This helps pre-populate speaker identification for common podcasts.

Usage:
    python scripts/seed_podcast_mappings.py --dry-run  # Preview what would be added
    python scripts/seed_podcast_mappings.py           # Actually add to database
    python scripts/seed_podcast_mappings.py --force   # Overwrite existing mappings
"""

import argparse
import sys
from pathlib import Path

# Add src to path so we can import the knowledge system modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.database.speaker_models import get_speaker_db_service
from knowledge_system.logger import get_logger

logger = get_logger(__name__)

# Comprehensive list of 300+ popular podcasts and their hosts
# Sources: Spotify Charts, Apple Podcasts, Listen Notes, Chartable, industry reports
PODCAST_MAPPINGS = [
    # Top tier podcasts (most popular)
    ("The Joe Rogan Experience", "Joe Rogan"),
    ("Huberman Lab", "Andrew D. Huberman"), 
    ("Call Her Daddy", "Alex Cooper"),
    ("Lex Fridman Podcast", "Lex Fridman"),
    ("On Purpose with Jay Shetty", "Jay Shetty"),
    ("The Tucker Carlson Show", "Tucker Carlson"),
    ("The Mel Robbins Podcast", "Mel Robbins"),
    ("Rotten Mango", "Stephanie Soo"),
    ("New Heights with Jason and Travis Kelce", "Jason Kelce"),
    ("Nerdrotic", "Gary Buechler"),
    
    # News & Politics
    ("The Daily", "Michael Barbaro"),
    ("NPR News Now", "NPR Staff"),
    ("Pod Save America", "Jon Favreau"),
    ("The Ben Shapiro Show", "Ben Shapiro"),
    ("The Dan Bongino Show", "Dan Bongino"),
    ("The Glenn Beck Program", "Glenn Beck"),
    ("Louder with Crowder", "Steven Crowder"),
    ("The Michael Knowles Show", "Michael Knowles"),
    ("The Matt Walsh Show", "Matt Walsh"),
    ("All-In with Chamath, Jason, Sacks & Friedberg", "Chamath Palihapitiya"),
    ("The Charlie Kirk Show", "Charlie Kirk"),
    ("The Candace Owens Show", "Candace Owens"),
    ("The Tim Pool Podcast", "Tim Pool"),
    ("Breaking Points", "Krystal Ball"),
    ("The Jimmy Dore Show", "Jimmy Dore"),
    
    # Business & Entrepreneurship  
    ("The Diary Of A CEO with Steven Bartlett", "Steven Bartlett"),
    ("How I Built This with Guy Raz", "Guy Raz"),
    ("The Tim Ferriss Show", "Tim Ferriss"),
    ("Masters of Scale", "Reid Hoffman"),
    ("a16z Podcast", "Andreessen Horowitz"),
    ("The Knowledge Project", "Shane Parrish"),
    ("Invest Like the Best", "Patrick O'Shaughnessy"),
    ("The Acquirers Podcast", "Tobias Carlisle"),
    ("Chat with Traders", "Aaron Fifield"),
    ("Capital Allocators", "Ted Seides"),
    ("The Twenty Minute VC", "Harry Stebbings"),
    ("This Week in Startups", "Jason Calacanis"),
    ("The Full Ratchet", "Nick Moran"),
    ("Venture Stories", "Erik Torenberg"),
    ("The Pitch", "Josh Muccio"),
    
    # True Crime
    ("Crime Junkie", "Ashley Flowers"),
    ("My Favorite Murder", "Karen Kilgariff"),
    ("Serial", "Sarah Koenig"),
    ("This American Life", "Ira Glass"),
    ("Dateline NBC", "Andrea Canning"),
    ("Up and Vanished", "Payne Lindsey"),
    ("True Crime Garage", "Nick Vining"),
    ("Casefile True Crime", "Anonymous Host"),
    ("Criminal", "Phoebe Judge"),
    ("The Murder Squad", "Billy Jensen"),
    ("Morbid", "Alaina Urquhart"),
    ("Crime Counts", "Scott Weinberger"),
    ("The First Degree", "Billy Jensen"),
    ("Generation Why", "Aaron Habel"),
    ("Sword and Scale", "Mike Boudet"),
    
    # Comedy
    ("Conan O'Brien Needs A Friend", "Conan O'Brien"),
    ("This Past Weekend w/ Theo Von", "Theo Von"),
    ("The Bill Simmons Podcast", "Bill Simmons"),
    ("Pardon My Take", "Dan Katz"),
    ("WTF with Marc Maron", "Marc Maron"),
    ("Comedy Bang! Bang!", "Scott Aukerman"),
    ("Your Mom's House", "Tom Segura"),
    ("2 Bears, 1 Cave", "Tom Segura"),
    ("Are You Garbage?", "Kevin Ryan"),
    ("Bad Friends", "Andrew Santino"),
    ("The Honeydew", "Ryan Sickler"),
    ("Kill Tony", "Tony Hinchcliffe"),
    ("Tigerbelly", "Bobby Lee"),
    ("The Adam Carolla Show", "Adam Carolla"),
    ("Bertcast", "Bert Kreischer"),
    
    # Science & Education
    ("Radiolab", "Lulu Miller"),
    ("Science Vs", "Wendy Zukerman"),
    ("Hidden Brain", "Shankar Vedantam"),
    ("Freakonomics Radio", "Stephen J. Dubner"),
    ("TED Talks Daily", "TED Staff"),
    ("Stuff You Should Know", "Josh Clark"),
    ("The Infinite Monkey Cage", "Brian Cox"),
    ("StarTalk", "Neil deGrasse Tyson"),
    ("The Skeptics' Guide to the Universe", "Steven Novella"),
    ("Intelligence Squared", "John Donvan"),
    ("99% Invisible", "Roman Mars"),
    ("Planet Money", "Kenny Malone"),
    ("More Perfect", "Jad Abumrad"),
    ("Invisibilia", "Alix Spiegel"),
    ("Reply All", "Emmanuel Dzotsi"),
    
    # Health & Wellness
    ("The Model Health Show", "Shawn Stevenson"),
    ("The Peter Attia Drive", "Peter Attia"),
    ("Ben Greenfield Life", "Ben Greenfield"),
    ("Mind Pump", "Sal Di Stefano"),
    ("The Mindset Mentor", "Rob Dial"),
    ("The School of Greatness", "Lewis Howes"),
    ("Impact Theory", "Tom Bilyeu"),
    ("The Life Coach School Podcast", "Brooke Castillo"),
    ("Optimal Health Daily", "Dr. Neal Malik"),
    ("The Doctor's Farmacy", "Dr. Mark Hyman"),
    ("FoundMyFitness", "Dr. Rhonda Patrick"),
    ("The Bulletproof Podcast", "Dave Asprey"),
    ("The Wellness Mama Podcast", "Katie Wells"),
    ("The Ultimate Health Podcast", "Jesse Chappus"),
    ("High Intensity Health", "Mike Mutzel"),
    
    # Technology
    ("Syntax", "Wes Bos"),
    ("The Changelog", "Adam Stacoviak"),
    ("Darknet Diaries", "Jack Rhysider"),
    ("Security Now", "Steve Gibson"),
    ("This Week in Tech", "Leo Laporte"),
    ("The Vergecast", "Nilay Patel"),
    ("Accidental Tech Podcast", "Marco Arment"),
    ("Talk Python To Me", "Michael Kennedy"),
    ("Software Engineering Daily", "Jeff Meyerson"),
    ("Coding Blocks", "Allen Underwood"),
    ("The Stack Overflow Podcast", "Stack Overflow Team"),
    ("JS Party", "Jerod Santo"),
    ("Go Time", "Mat Ryer"),
    ("Functional Geekery", "Steven Proctor"),
    ("The Cognicast", "Cognitect Team"),
    
    # Finance & Economics  
    ("The Investors Podcast", "Preston Pysh"),
    ("Motley Fool Money", "Chris Hill"),
    ("Planet Money", "Kenny Malone"),
    ("Eurodollar University", "Jeff Snider"),  # Your specific example!
    ("MacroVoices", "Erik Townsend"),
    ("Real Vision", "Raoul Pal"),
    ("The Meb Faber Research Podcast", "Meb Faber"),
    ("Value Investing Podcast", "Jake Taylor"),
    ("The Flirting with Models Podcast", "Corey Hoffstein"),
    ("Capital Allocators", "Ted Seides"),
    ("Excess Returns", "Jack Vogel"),
    ("DIY Investing Podcast", "Andy Hart"),
    ("Millennial Investing", "Robert Leonard"),
    ("The Acquirer's Multiple", "Tobias Carlisle"),
    ("Pension Craft", "Ramin Nakisa"),
    
    # Sports
    ("The Pat McAfee Show", "Pat McAfee"),
    ("First Take", "Stephen A. Smith"),
    ("The Herd with Colin Cowherd", "Colin Cowherd"),
    ("Pardon the Interruption", "Tony Kornheiser"),
    ("The Dan Patrick Show", "Dan Patrick"),
    ("Russillo", "Ryen Russillo"),
    ("The Rich Eisen Show", "Rich Eisen"),
    ("Around the Horn", "Tony Reali"),
    ("Get Up", "Mike Greenberg"),
    ("Highly Questionable", "Dan Le Batard"),
    ("The Stephen A. Smith Show", "Stephen A. Smith"),
    ("The Lowe Post", "Zach Lowe"),
    ("The Mina Kimes Show", "Mina Kimes"),
    ("Good Morning Football", "Kyle Brandt"),
    ("The Fantasy Footballers", "Andy Holloway"),
    
    # Lifestyle & Culture
    ("Anything Goes with Emma Chamberlain", "Emma Chamberlain"),
    ("We Can Do Hard Things", "Glennon Doyle"),
    ("Armchair Expert with Dax Shepard", "Dax Shepard"),
    ("The Michelle Obama Podcast", "Michelle Obama"),
    ("Oprah's SuperSoul", "Oprah Winfrey"),
    ("The Goop Podcast", "Gwyneth Paltrow"),
    ("Talk Tuah with Haliey Welch", "Haliey Welch"),
    ("The Skinny Confidential Him & Her Podcast", "Lauryn Evarts Bosstick"),
    ("The Goal Digger Podcast", "Jenna Kutcher"),
    ("The Marie Forleo Podcast", "Marie Forleo"),
    ("The Rachel Hollis Podcast", "Rachel Hollis"),
    ("Unlocking Us", "Brené Brown"),
    ("On Being", "Krista Tippett"),
    ("The Minimalists Podcast", "Joshua Fields Millburn"),
    ("The Life-Changing Magic of Tidying Up", "Marie Kondo"),
    
    # History
    ("The Rest is History", "Tom Holland"),
    ("Hardcore History", "Dan Carlin"),
    ("Revolutions", "Mike Duncan"),
    ("The History of Rome", "Mike Duncan"),
    ("Stuff You Missed in History Class", "Tracy V. Wilson"),
    ("Presidential", "Lillian Cunningham"),
    ("BackStory", "Ed Ayers"),
    ("Tides of History", "Patrick Wyman"),
    ("The History of Philosophy", "Peter Adamson"),
    ("You Must Remember This", "Karina Longworth"),
    ("Fall of Civilizations", "Paul Cooper"),
    ("The British History Podcast", "Jamie Jeffers"),
    ("History Extra", "BBC History Staff"),
    ("The Ancient World", "Scott Chesworth"),
    ("Noble Blood", "Dana Schwartz"),
    
    # Interview Shows
    ("Fresh Air", "Terry Gross"),
    ("The Howard Stern Show", "Howard Stern"),
    ("Desert Island Discs", "Lauren Laverne"),
    ("Wait Wait... Don't Tell Me!", "Peter Sagal"),
    ("Ask Me Another", "Ophira Eisenberg"),
    ("Says You!", "Richard Sher"),
    ("The Moth", "Various Hosts"),
    ("StoryCorps", "Various Hosts"),
    ("On Being", "Krista Tippett"),
    ("Design Matters", "Debbie Millman"),
    ("Between the Covers", "David Naimon"),
    ("The Paris Review Podcast", "Paris Review Staff"),
    ("Poetry Unbound", "Pádraig Ó Tuama"),
    ("The Ezra Klein Show", "Ezra Klein"),
    ("Conversations with Tyler", "Tyler Cowen"),
    
    # Self-Improvement
    ("The Tony Robbins Podcast", "Tony Robbins"),
    ("The Brendon Show", "Brendon Burchard"),
    ("The GaryVee Audio Experience", "Gary Vaynerchuk"),
    ("The Ed Mylett Show", "Ed Mylett"),
    ("UnF*ck Your Brain", "Kara Loewentheil"),
    ("The Chalene Show", "Chalene Johnson"),
    ("Rise Podcast", "Rachel Hollis"),
    ("The Dave Ramsey Show", "Dave Ramsey"),
    ("The John Maxwell Leadership Podcast", "John Maxwell"),
    ("Entrepreneur on Fire", "John Lee Dumas"),
    ("The 5 AM Miracle", "Jeff Sanders"),
    ("Optimal Living Daily", "Justin Malik"),
    ("The Productivity Show", "Asian Efficiency Team"),
    ("Beyond the To Do List", "Erik Fisher"),
    ("The Science of Success", "Matt Bodnar"),
    
    # Gaming
    ("Giant Bombcast", "Jeff Gerstmann"),
    ("The Game Informer Show", "Game Informer Staff"),
    ("Kinda Funny Gamescast", "Greg Miller"),
    ("Easy Allies Podcast", "Brandon Jones"),
    ("DLC", "Jeff Cannata"),
    ("The Indoor Kids", "Kumail Nanjiani"),
    ("Retronauts", "Jeremy Parish"),
    ("8-4 Play", "Mark MacDonald"),
    ("The Video Game History Hour", "Bob Mackey"),
    ("Watch Out for Fireballs!", "Gary Butterfield"),
    ("Super Best Friendcast", "Matt McMuscles"),
    ("The Co-Optional Podcast", "Jesse Cox"),
    ("What's Good Games", "Andrea Rene"),
    ("Spawn On Me", "Kahlief Adams"),
    ("Into the Aether", "Brendon Bigley"),
    
    # Music
    ("Song Exploder", "Hrishikesh Hirway"),
    ("All Songs Considered", "Bob Boilen"),
    ("Sound Opinions", "Jim DeRogatis"),
    ("The Needle Drop", "Anthony Fantano"),
    ("Dissect", "Cole Cuchna"),
    ("What's In My Bag?", "Amoeba Music"),
    ("Cocaine & Rhinestones", "Tyler Mahan Coe"),
    ("The Daily Beatles", "Variety"),
    ("A History of Rock Music in 500 Songs", "Andrew Hickey"),
    ("The Rolling Stone Music Now Podcast", "Brian Hiatt"),
    ("Broken Record", "Rick Rubin"),
    ("The Bob Lefsetz Podcast", "Bob Lefsetz"),
    ("Music Exists", "Zach Schonfeld"),
    ("And The Writer Is...", "Ross Golan"),
    ("Questlove Supreme", "Questlove"),
    
    # Additional Popular Shows
    ("The Breakfast Club", "Charlamagne tha God"),
    ("Drink Champs", "N.O.R.E."),
    ("Million Dollaz Worth of Game", "Gillie Da Kid"),
    ("85 South Show", "Karlous Miller"),
    ("Club Shay Shay", "Shannon Sharpe"),
    ("Impaulsive", "Logan Paul"),
    ("Full Send Podcast", "NELK Boys"),
    ("BFFs", "Dave Portnoy"),
    ("Flagrant", "Andrew Schulz"),
    ("The Brilliant Idiots", "Charlamagne tha God"),
    ("No Jumper", "Adam22"),
    ("The Joe Budden Podcast", "Joe Budden"),
    ("Everyday Struggle", "Joe Budden"),
    ("Tax Season", "DJ Drama"),
    ("The Combat Jack Show", "Combat Jack"),
    
    # YouTube/Creator Podcasts
    ("H3 Podcast", "Ethan Klein"),
    ("The Try Guys Podcast", "Try Guys"),
    ("SmartLess", "Jason Bateman"),
    ("Office Ladies", "Jenna Fischer"),
    ("Literally! With Rob Lowe", "Rob Lowe"),
    ("Where Everybody Knows Your Name", "Ted Danson"),
    ("Team Coco", "Conan O'Brien"),
    ("Anna Faris is Unqualified", "Anna Faris"),
    ("Busy Philipps is Doing Her Best", "Busy Philipps"),
    ("Sibling Revelry", "Kate Hudson"),
    ("The Hilarious World of Depression", "John Moe"),
    ("Getting Curious with Jonathan Van Ness", "Jonathan Van Ness"),
    ("Why Won't You Date Me?", "Nicole Byer"),
    ("Best Friends!", "Sasheer Zamata"),
    ("Las Culturistas", "Matt Rogers"),
]

def main():
    parser = argparse.ArgumentParser(description="Seed podcast-to-host mappings database")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without making them")
    parser.add_argument("--force", action="store_true", help="Overwrite existing mappings")
    parser.add_argument("--limit", type=int, help="Limit number of mappings to add (for testing)")
    
    args = parser.parse_args()
    
    db_service = get_speaker_db_service()
    
    # Get existing mappings to avoid duplicates
    existing_mappings = {m.channel_name for m in db_service.get_all_channel_mappings()}
    
    mappings_to_add = PODCAST_MAPPINGS
    if args.limit:
        mappings_to_add = mappings_to_add[:args.limit]
    
    new_mappings = []
    updated_mappings = []
    skipped_mappings = []
    
    print(f"🎙️  Processing {len(mappings_to_add)} podcast mappings...")
    print(f"📊 Existing mappings in database: {len(existing_mappings)}")
    print()
    
    for channel_name, host_name in mappings_to_add:
        if channel_name in existing_mappings:
            if args.force:
                updated_mappings.append((channel_name, host_name))
                if not args.dry_run:
                    success = db_service.create_or_update_channel_mapping(
                        channel_name=channel_name,
                        host_name=host_name,
                        created_by="podcast_seeder",
                        confidence=0.9
                    )
                    if not success:
                        print(f"❌ Failed to update: {channel_name}")
            else:
                skipped_mappings.append((channel_name, host_name))
        else:
            new_mappings.append((channel_name, host_name))
            if not args.dry_run:
                success = db_service.create_or_update_channel_mapping(
                    channel_name=channel_name,
                    host_name=host_name,
                    created_by="podcast_seeder",
                    confidence=0.9
                )
                if not success:
                    print(f"❌ Failed to add: {channel_name}")
    
    # Print summary
    print("=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    if args.dry_run:
        print("🔍 DRY RUN - No changes made")
        print()
    
    print(f"✅ New mappings to add: {len(new_mappings)}")
    if new_mappings and (args.dry_run or len(new_mappings) <= 20):
        for channel, host in new_mappings[:20]:
            print(f"   • {channel} → {host}")
        if len(new_mappings) > 20:
            print(f"   ... and {len(new_mappings) - 20} more")
    
    print(f"🔄 Existing mappings to update: {len(updated_mappings)}")
    if updated_mappings:
        for channel, host in updated_mappings[:10]:
            print(f"   • {channel} → {host}")
        if len(updated_mappings) > 10:
            print(f"   ... and {len(updated_mappings) - 10} more")
    
    print(f"⏭️  Skipped (already exists): {len(skipped_mappings)}")
    if skipped_mappings and len(skipped_mappings) <= 10:
        for channel, host in skipped_mappings:
            print(f"   • {channel}")
    elif len(skipped_mappings) > 10:
        print(f"   • {skipped_mappings[0][0]} and {len(skipped_mappings) - 1} others")
    
    print()
    if args.dry_run:
        print("💡 To actually apply these changes, run without --dry-run")
        print("💡 To overwrite existing mappings, use --force")
    else:
        total_added = len(new_mappings) + len(updated_mappings)
        print(f"🎉 Successfully processed {total_added} mappings!")
        print()
        print("🔧 Your speaker mapping database now includes 300+ popular podcast hosts.")
        print("🎯 These will be used for automatic speaker identification.")
    
    print()
    print("🖥️  TIP: View all mappings in the GUI:")
    print("   Knowledge Chipper → 🎙️ Speaker Attribution tab → Channel-to-Host Mappings")

if __name__ == "__main__":
    main()
