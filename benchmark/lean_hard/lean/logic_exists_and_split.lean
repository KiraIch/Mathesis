import Mathlib
namespace MathesisHard
theorem lean_logic_exists_and_split : ∀ (α : Type) (P Q : α → Prop), (∃ x, P x ∧ Q x) → (∃ x, P x) ∧ (∃ x, Q x) := by
  intro α P Q h
  obtain ⟨x, hp, hq⟩ := h
  exact ⟨⟨x, hp⟩, ⟨x, hq⟩⟩
end MathesisHard
