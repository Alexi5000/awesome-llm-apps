# Dependency maintenance

The requirements retain the podcast, browser-search, local audio, RSS, scraping, HTTP, database and worker integrations. Runtime coverage is in `tests/test_dependency_runtime.py` and the Beifong CI workflow.

LangChain, its provider wrappers/text splitters and Mem0 were leftovers from an older frozen environment. No Python import, dynamic loader, application configuration or documentation in this example references them. Browser-use 0.5.11 uses its native model adapters here; its optional LangChain extras are not requested. These ten unused direct pins have been removed. A fresh environment and the complete runtime suite verify that browser search, podcast storage and local media behavior still work without those packages. No application feature or example was removed.

The Transformers 5 upgrade is paired with its required Hub, tokenizer, safetensors, regex and Click versions. Tests run the actual sentence-transformer bag-of-words encoder and Kokoro Albert network on CPU without downloading pretrained models. Full model downloads and live provider execution require separate deployment validation.

Known upstream advisories may still affect dependencies without a released fix. A passing install or runtime suite does not establish a clean security audit; retain the separate audit results when updating these pins.
