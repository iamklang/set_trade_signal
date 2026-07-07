# Data Model — {{FEATURE_NAME}}

**Feature ID:** {{NNN-feature-name}} | Created: {{DATE}}

## Entity: {{EntityName}}
| Field | Type | Constraints | คำอธิบาย |
|-------|------|-------------|----------|
| `id` | {{...}} | PK | {{...}} |
| `{{field}}` | {{...}} | {{...}} | {{...}} |

### Validation Rules
- {{กฎ validation}}

### State Transitions
{{ถ้ามี: [state A] --action--> [state B]}}

### SQL Schema (ถ้าใช้ DB)
```sql
{{CREATE TABLE ...}}
```
