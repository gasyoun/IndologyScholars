.PHONY: all db analytics data pages scholars validate

all: db analytics data scholars pages validate

db:
	python build_and_populate_db.py

analytics:
	python generate_analytics.py

data:
	python generate_site_data.py

scholars:
	python generate_scholars_pages.py

pages:
	python generate_publication_pages.py

validate:
	python validate_publication.py
