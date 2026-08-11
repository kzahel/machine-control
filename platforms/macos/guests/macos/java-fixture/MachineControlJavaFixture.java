import java.awt.BorderLayout;
import java.awt.FlowLayout;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import javax.swing.JButton;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.SwingUtilities;
import javax.swing.WindowConstants;

public final class MachineControlJavaFixture {
    private int count;
    private final JLabel countLabel = new JLabel("Java count: 0");
    private final Path stateRoot = Path.of(
        System.getProperty("user.home"), "Library", "Caches",
        "machine-control-java-fixture");
    private final Path statePath = stateRoot.resolve("state.json");

    private void writeState(String effect) {
        try {
            Files.createDirectories(stateRoot);
            Path temporary = stateRoot.resolve("state.json.new");
            String json = String.format(
                "{\"framework\":\"Java Swing\",\"count\":%d,"
                + "\"effect\":\"%s\"}%n", count, effect);
            Files.writeString(temporary, json, StandardCharsets.UTF_8);
            Files.move(temporary, statePath,
                StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.ATOMIC_MOVE);
        } catch (Exception error) {
            System.err.println("Java fixture state write failed: " + error);
        }
    }

    private void update(String effect) {
        if (effect.equals("incremented")) count += 1;
        if (effect.equals("reset")) count = 0;
        countLabel.setText("Java count: " + count);
        writeState(effect);
    }

    private void show() {
        JFrame frame = new JFrame("Machine Control Java Fixture");
        frame.setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);

        JLabel heading = new JLabel("Java Swing semantic fixture");
        JButton increment = new JButton("Increment Java");
        JButton reset = new JButton("Reset Java");
        increment.getAccessibleContext().setAccessibleName("Increment Java");
        reset.getAccessibleContext().setAccessibleName("Reset Java");
        increment.addActionListener(event -> update("incremented"));
        reset.addActionListener(event -> update("reset"));

        JPanel buttons = new JPanel(new FlowLayout(FlowLayout.LEADING));
        buttons.add(increment);
        buttons.add(reset);
        JPanel content = new JPanel(new BorderLayout(12, 12));
        content.setBorder(javax.swing.BorderFactory.createEmptyBorder(
            24, 24, 24, 24));
        content.add(heading, BorderLayout.NORTH);
        content.add(countLabel, BorderLayout.CENTER);
        content.add(buttons, BorderLayout.SOUTH);
        frame.setContentPane(content);
        frame.setSize(520, 280);
        frame.setLocationByPlatform(true);
        frame.setVisible(true);
        writeState("launched");
    }

    public static void main(String[] arguments) {
        System.setProperty(
            "apple.awt.application.name", "Machine Control Java Fixture");
        SwingUtilities.invokeLater(() -> new MachineControlJavaFixture().show());
    }
}
