import Mathlib
namespace MathesisHard
theorem lean_set_inter_mono : ∀ (α : Type) (A B C : Set α), A ⊆ B → A ∩ C ⊆ B ∩ C := by
  intro α A B C h x hx
  exact ⟨h hx.1, hx.2⟩
end MathesisHard
