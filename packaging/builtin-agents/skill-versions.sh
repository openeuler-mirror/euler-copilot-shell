# Skill versions and slugs — single source of truth.
# Sourced by prepare-release.sh and referenced by the RPM spec.
#
# Each variable follows the pattern:
#   SKILL_<NAME>_SLUG=...
#   SKILL_<NAME>_VERSION=...
#
# Update versions here when upstream skills are upgraded.
# Skills are downloaded from SkillHub registry via:
#   https://api.skillhub.cn/api/v1/download?slug=<slug>

SKILL_MANPAGE_SLUG=manpage-skill
SKILL_MANPAGE_VERSION=1.0.0

SKILL_LOG_ANOMALY_SLUG=log-anomaly-detector
SKILL_LOG_ANOMALY_VERSION=1.0.0

SKILL_HTML_REPORT_SLUG=html-report-generator
SKILL_HTML_REPORT_VERSION=1.0.0

SKILL_BRAINSTORM_SLUG=brainstorm-beagle
SKILL_BRAINSTORM_VERSION=1.0.5

SKILL_PLANTUML_SLUG=plantuml-skill
SKILL_PLANTUML_VERSION=1.4.1
