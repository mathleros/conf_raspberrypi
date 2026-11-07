#!/bin/bash

find src/irobot -name "*.py" -not -name "__init__.py" | sort | while IFS= read -r f; do  echo "### FILE: $f"
cat "$f"
echo
done > irobot_src_all.txt

find src/irobot -name "*.md" | sort | while IFS= read -r f; do  echo "### FILE: $f"
cat "$f"
echo
done > irobot_docs_all.txt

find tests -name "*.py" -not -name "__init__.py" | sort | while IFS= read -r f; do  echo "### FILE: $f"
cat "$f"
echo
done > irobot_test_all.txt
