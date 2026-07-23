# Diagram Sources

All diagrams are authored in **Mermaid** so they stay version-controlled, diff-able and
reproducible. Nothing here is a screenshot.

| File | Diagram |
|------|---------|
| `01_use_case.mermaid` | Use Case Diagram |
| `02_class_diagram.mermaid` | Class Diagram (agent + service layers) |
| `03_sequence_patient_arrival.mermaid` | Sequence Diagram — patient arrival end-to-end |
| `04_activity_diagram.mermaid` | Activity Diagram — triage to executive approval |
| `05_er_diagram.mermaid` | Entity Relationship Diagram |
| `06_component_diagram.mermaid` | Component Diagram |
| `07_deployment_diagram.mermaid` | Deployment Diagram |
| `08_dfd_level0.mermaid` | Data Flow Diagram — Level 0 (context) |
| `09_dfd_level1.mermaid` | Data Flow Diagram — Level 1 |

## Rendering to PNG / SVG

```bash
npm install -g @mermaid-js/mermaid-cli
cd docs/diagrams
for f in *.mermaid; do
  mmdc -i "$f" -o "figures/${f%.mermaid}.png" -w 2400 -b white
done
```

Or paste any file into <https://mermaid.live> for an interactive render.

The `scripts/render_diagrams.sh` helper does the whole batch in one command.
