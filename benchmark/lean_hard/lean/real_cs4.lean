import Mathlib
namespace MathesisHard
theorem lean_real_cs4 : ∀ x y z w : ℝ, (x * y + z * w) ^ 2 ≤ (x ^ 2 + z ^ 2) * (y ^ 2 + w ^ 2) := by
  intro x y z w
  have h := sq_nonneg (x * w - z * y)
  nlinarith [h]
end MathesisHard
