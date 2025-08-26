For normal pushes and patch bumps:
Run 
./push_to_github.sh
 and confirm the prompt. It will:
Bump patch version via scripts/bump_version.py
Stage, commit with the new version, and push
For manual minor/major bumps:

python3 scripts/bump_version.py --part minor (or --part major)

Then commit/push as usual