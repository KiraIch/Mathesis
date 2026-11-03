import Mathlib
namespace MathesisHard
theorem lean_logic_dne_em : ∀ (P : Prop), ¬¬(P ∨ ¬P) := by
  intro P h
  apply h
  right
  intro p
  apply h
  left
  exact p
end MathesisHard
