import Mathlib
namespace MathesisHard
theorem lean_ineq_cyc_sq_over_lin : ∀ a b c : ℝ, 0 < a → 0 < b → 0 < c → a + b + c ≤ a ^ 2 / b + b ^ 2 / c + c ^ 2 / a := by
  intro a b c ha hb hc
  have k : ∀ x y : ℝ, 0 < x → 0 < y → 2 * x - y ≤ x ^ 2 / y := by
    intro x y hx hy
    rw [le_div_iff₀ hy]
    nlinarith [sq_nonneg (x - y)]
  have h1 := k a b ha hb
  have h2 := k b c hb hc
  have h3 := k c a hc ha
  linarith
end MathesisHard
