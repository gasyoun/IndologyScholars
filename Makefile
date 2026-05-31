.PHONY: all db analytics data pages pages-final scholars guardrails validate

all: db analytics data scholars pages guardrails pages-final validate

db:
	python build_and_populate_db.py

analytics:
	python generate_analytics.py
	python article/work_title_keywords.py
	python tools/build_classification_reliability_sample.py

data:
	python generate_site_data.py

scholars:
	python generate_scholars_pages.py

pages:
	python generate_publication_pages.py

guardrails:
	python tools/build_scientometrics_guardrails.py
	python tools/build_human_review_index.py

pages-final:
	python generate_publication_pages.py

validate:
	python validate_publication.py

clean:
	python -c "import pathlib; [p.unlink() for p in pathlib.Path('.').glob('site_data_timeline_*.json')]; [p.unlink() for p in pathlib.Path('p').glob('*.html') if p.is_file()]; [p.unlink() for p in pathlib.Path('s').glob('*.html') if p.is_file()]; [p.unlink() for p in pathlib.Path('themes').glob('*.html') if p.name != 'index.html']"

