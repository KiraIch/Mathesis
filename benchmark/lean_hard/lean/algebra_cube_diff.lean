import Mathlib
namespace MathesisHard
theorem lean_algebra_cube_diff : ∀ (R : Type) [CommRing R] (a b : R), (a + b) ^ 3 - (a - b) ^ 3 = 6 * a ^ 2 * b + 2 * b ^ 3 := by
  intro R _ a b
  ring
end MathesisHard
