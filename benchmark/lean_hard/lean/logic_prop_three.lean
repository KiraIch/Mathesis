import Mathlib
namespace MathesisHard
theorem lean_logic_prop_three : ∀ (P Q R : Prop), (P → Q) → (Q → R) → ¬R → ¬P := by
  intro P Q R hpq hqr hnr hp
  exact hnr (hqr (hpq hp))
end MathesisHard
