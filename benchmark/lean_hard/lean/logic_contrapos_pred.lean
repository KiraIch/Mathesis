import Mathlib
namespace MathesisHard
theorem lean_logic_contrapos_pred : ∀ (α : Type) (p q : α → Prop), (∀ x, p x → q x) → ∀ x, ¬ q x → ¬ p x := by
  intro α p q h x hq hp
  exact hq (h x hp)
end MathesisHard
