import Mathlib
namespace MathesisHard
theorem lean_set_inter_assoc_sub : ∀ (α : Type) (A B C : Set α), (A ∩ B) ∩ C ⊆ A ∩ (B ∩ C) := by
  intro α A B C x hx
  exact ⟨hx.1.1, hx.1.2, hx.2⟩
end MathesisHard
