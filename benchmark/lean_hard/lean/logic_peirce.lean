import Mathlib
namespace MathesisHard
theorem lean_logic_peirce : ∀ (P Q : Prop), ((P → Q) → P) → P := by
  intro P Q h
  by_contra hp
  exact hp (h (fun p => absurd p hp))
end MathesisHard
