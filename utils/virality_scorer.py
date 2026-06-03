"""
ViralClip AI — Virality Scorer
Converts Groq's multi-dimensional scores into a 0-100 virality rating.
"""


class ViralityScorer:
    """
    Weighted scoring system that converts 8 dimension scores (0-10 each)
    into a final 0-100 virality rating optimized for short-form viral content.
    """

    WEIGHTS = {
        "curiosity_hook":      0.20,   # Biggest driver — scroll-stopping power
        "retention":           0.18,   # Watch-through rate signal
        "emotional_intensity": 0.15,   # Shares driven by emotion
        "audience_hook":       0.13,   # Relevance to target audience
        "novelty":             0.12,   # Surprise factor = comment magnet
        "storytelling":        0.10,   # Narrative completion keeps watching
        "controversy":         0.07,   # Debate = comment section activity
        "educational_value":   0.05,   # Saves + bookmarks signal
    }

    def compute_score(self, scores: dict) -> int:
        """
        Compute weighted virality score from Groq's dimension scores.
        Returns integer 0-100.
        """
        if not scores:
            return 0

        total = 0.0
        total_weight = 0.0

        for dim, weight in self.WEIGHTS.items():
            raw = scores.get(dim, 0)
            # Normalize raw score: Groq returns 0-10, we need 0-100
            normalized = float(raw) * 10
            # Apply weight
            total += normalized * weight
            total_weight += weight

        if total_weight == 0:
            return 0

        score = total / total_weight
        return max(0, min(100, round(score)))

    def get_score_breakdown(self, scores: dict) -> dict:
        """Return detailed breakdown with weighted contributions."""
        breakdown = {}
        for dim, weight in self.WEIGHTS.items():
            raw = float(scores.get(dim, 0))
            contribution = raw * 10 * weight
            breakdown[dim] = {
                "raw": raw,
                "weight": weight,
                "contribution": round(contribution, 2),
                "label": self._get_label(dim, raw),
            }
        return breakdown

    def get_score_label(self, score: int) -> str:
        """Human-readable label for a virality score."""
        if score >= 90:
            return "🔥 VIRAL POTENTIAL"
        elif score >= 75:
            return "⚡ HIGH POTENTIAL"
        elif score >= 60:
            return "✅ GOOD CLIP"
        elif score >= 45:
            return "📊 AVERAGE"
        else:
            return "💤 LOW POTENTIAL"

    def _get_label(self, dimension: str, score: float) -> str:
        labels = {
            "curiosity_hook": ["No hook", "Weak hook", "OK hook", "Good hook", "Strong hook", "🔥 Viral hook"],
            "retention": ["Won't watch", "Low retention", "OK retention", "Good retention", "High retention", "🔒 Binge-worthy"],
            "emotional_intensity": ["Flat", "Mild emotion", "Some emotion", "Emotional", "High emotion", "💥 Explosive"],
            "audience_hook": ["Generic", "Niche miss", "Somewhat relevant", "Relevant", "Highly targeted", "🎯 Perfect fit"],
            "novelty": ["Overdone", "Common", "Somewhat fresh", "Fresh take", "Novel", "🤯 Never seen before"],
            "storytelling": ["No arc", "Loose story", "Basic arc", "Clear arc", "Compelling arc", "📖 Masterful"],
            "controversy": ["Boring safe", "Slight tension", "Some debate", "Controversial", "Highly divisive", "🌋 Culture war"],
            "educational_value": ["No value", "Minimal", "Some value", "Useful", "Very useful", "🎓 Must-save"],
        }
        bucket = min(5, int(score / 2))
        return labels.get(dimension, [""] * 6)[bucket]
