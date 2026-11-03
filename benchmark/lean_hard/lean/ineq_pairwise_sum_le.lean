import Mathlib
namespace MathesisHard
theorem lean_ineq_pairwise_sum_le : ∀ a b c : ℝ, a * b + b * c + c * a ≤ a ^ 2 + b ^ 2 + c ^ 2 := by
  intro a b c
  nlinarith [sq_nonneg (a - b), sq_nonneg (b - c), sq_nonneg (c - a)]
end MathesisHard
