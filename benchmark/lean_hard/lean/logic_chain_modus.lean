import Mathlib
namespace MathesisHard
theorem lean_logic_chain_modus : ∀ (P Q R : Prop), (P → Q) → (R → P) → R → Q := by
  intro P Q R hpq hrp hr
  exact hpq (hrp hr)
end MathesisHard
