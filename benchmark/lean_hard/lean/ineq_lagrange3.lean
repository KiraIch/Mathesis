import Mathlib
namespace MathesisHard
theorem lean_ineq_lagrange3 : ∀ a1 a2 a3 b1 b2 b3 : ℝ, (a1 * b1 + a2 * b2 + a3 * b3) ^ 2 ≤ (a1 ^ 2 + a2 ^ 2 + a3 ^ 2) * (b1 ^ 2 + b2 ^ 2 + b3 ^ 2) := by
  intro a1 a2 a3 b1 b2 b3
  have h1 := sq_nonneg (a1 * b2 - a2 * b1)
  have h2 := sq_nonneg (a2 * b3 - a3 * b2)
  have h3 := sq_nonneg (a1 * b3 - a3 * b1)
  nlinarith [h1, h2, h3]
end MathesisHard
