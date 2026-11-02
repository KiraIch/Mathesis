namespace MathesisPilot
theorem lean_nat_add_zero : ∀ (n : Nat), n + 0 = n := by
  intro n
  exact Nat.add_zero n
end MathesisPilot
