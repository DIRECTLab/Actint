```diagram
activity_intelligence/

├── pyproject.toml
├── .env

├── common/
│   ├── llm/
│   │   ├── model.py          # loads transformers model
│   │   ├── queue.py          # GPU queue (CRITICAL)
│   │   └── inference.py      # unified inference interface
│   │
│   ├── state/
│   │   └── base_state.py
│   │
│   └── utils/
│       └── logging.py

├── orchestrator/
│   ├── graph.py
│   ├── state.py
│   ├── router.py
│   └── nodes/
│       ├── route_task.py
│       ├── run_ais.py
│       ├── run_adsb.py
│       └── merge_results.py

├── agents/
│   ├── ais/
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── tools.py
│   │   └── nodes/
│   │       ├── fetch.py
│   │       ├── filter.py
│   │       ├── analyze.py
│   │       └── summarize.py
│   │
│   ├── adsb/
│       ├── graph.py
│       ├── state.py
│       ├── tools.py
│       └── nodes/
│           ├── fetch.py
│           ├── correlate.py
│           ├── detect.py
│           └── summarize.py

├── services/
│   └── scheduler.py          # optional (future Celery / scaling)

├── tests/
│   ├── test_ais.py
│   ├── test_adsb.py
│   └── test_orchestrator.py
```