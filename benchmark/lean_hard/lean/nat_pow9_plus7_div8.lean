import Mathlib
namespace MathesisHard
theorem lean_nat_pow9_plus7_div8 : ∀ n : ℕ, 8 ∣ 9 ^ n + 7 := by
  intro n
  induction n with | zero => simp | succ k ih => rw [pow_succ]; omega
end MathesisHard
