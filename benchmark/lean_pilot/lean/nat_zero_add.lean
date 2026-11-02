namespace MathesisPilot
theorem lean_nat_zero_add : ∀ (n : Nat), 0 + n = n := by
  intro n
  exact Nat.zero_add n
end MathesisPilot
