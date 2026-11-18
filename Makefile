.PHONY: test train evaluate serve

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

train:
	python scripts/build_dataset.py
	python scripts/fetch_sms_dataset.py
	PYTHONPATH=src python scripts/train_models.py
	python scripts/train_spam_model.py

evaluate:
	PYTHONPATH=src python scripts/evaluate_agent.py
	PYTHONPATH=src python scripts/benchmark_agent.py

serve:
	PYTHONPATH=src python -m notice_agent.server --port 8765
