import Mathlib
namespace MathesisHard
theorem lean_ineq_sum_sq_over_sum_cyc : ∀ a b c : ℝ, 0 < a → 0 < b → 0 < c → a + b + c = 3 → 3 / 2 ≤ a ^ 2 / (a + b) + b ^ 2 / (b + c) + c ^ 2 / (c + a) := by
  intro a b c ha hb hc h
  have k : ∀ x y : ℝ, 0 < x → 0 < y → (3 * x - y) / 4 ≤ x ^ 2 / (x + y) := by
    intro x y hx hy
    rw [le_div_iff₀ (by positivity)]
    nlinarith [sq_nonneg (x - y)]
  have h1 := k a b ha hb
  have h2 := k b c hb hc
  have h3 := k c a hc ha
  linarith
end MathesisHard
