.PHONY: test hce-smoketest
test:
	pytest -q

hce-smoketest:
	python scripts/run_episode.py docs/architecture/sample_episode.json --outdir out || true
