namespace MathesisPilot
theorem lean_nat_succ_add : ∀ (n m : Nat), Nat.succ n + m = Nat.succ (n + m) := by
  intro n
  intro m
  exact Nat.succ_add n m
end MathesisPilot
