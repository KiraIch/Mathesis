import Mathlib
namespace MathesisHard
theorem lean_algebra_sq_sum3 : ∀ x y z : ℤ, (x + y + z) ^ 2 - x ^ 2 - y ^ 2 - z ^ 2 = 2 * (x * y + y * z + z * x) := by
  intro x y z
  ring
end MathesisHard
