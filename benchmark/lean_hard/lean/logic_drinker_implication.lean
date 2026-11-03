import Mathlib
namespace MathesisHard
theorem lean_logic_drinker_implication : ∀ (α : Type) [Nonempty α] (P Q : α → Prop), ∃ x, ((P x → Q x) → ∀ y, P y → Q y) := by
  intro α _ P Q
  classical
  by_cases h : ∀ y, P y → Q y
  · obtain ⟨x⟩ := ‹Nonempty α›
    exact ⟨x, fun _ => h⟩
  · have hce : ∃ y, P y ∧ ¬ Q y := by push Not at h; exact h
    obtain ⟨y, hy, hq⟩ := hce
    exact ⟨y, fun hh => absurd (hh hy) hq⟩
end MathesisHard
