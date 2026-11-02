import Mathlib
namespace MathesisPilot
theorem lean_sum_sq_nonneg : ∀ (a b : ℝ), 0 ≤ a ^ 2 + b ^ 2 := by
  intro a
  intro b
  have h1 : 0 ≤ a ^ 2 := sq_nonneg a
  have h2 : 0 ≤ b ^ 2 := sq_nonneg b
  exact add_nonneg h1 h2
end MathesisPilot
