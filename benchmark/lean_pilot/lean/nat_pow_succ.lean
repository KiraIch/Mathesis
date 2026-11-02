namespace MathesisPilot
theorem lean_nat_pow_succ : ∀ (a n : Nat), a ^ (n + 1) = a ^ n * a := by
  intro a
  intro n
  exact Nat.pow_succ a n
end MathesisPilot
